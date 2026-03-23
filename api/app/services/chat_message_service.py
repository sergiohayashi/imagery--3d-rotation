import asyncio
import logging
import traceback
from datetime import datetime, timezone
from typing import List, Any

from bson import ObjectId
from fastapi import HTTPException
from pymongo import DESCENDING
from starlette import status

from app.services.services_for_rag.rag_strategy_vanilla import VanillaRag
from app.services.services_for_rag.rag_strategy_with_keyword_search import (
    RagContextBuilderWithTextSearch,
)
from app.utils.file_utils import guess_content_type_from_filename
from ..config.config import config
from ..database_async import db_async as db  # <-- use async DB
from ..llm_services.any_model import AnyModel
from ..models.chat_message import (
    ChatMessage,
    ChatResponse,
    ChatMessageNext,
    OutputTypes,
    ModelWithParameters,
)

logger = logging.getLogger(__name__)


def filter_meta(entries: List[dict]) -> List[dict]:
    r = []
    for e in entries:
        d = {**e}
        if e.get("meta"):
            d["meta"] = {
                "model": e["meta"].get("model"),
                "estimate_price": e["meta"].get("estimate_price"),
                "elapsed_in_sec": e["meta"].get("elapsed_in_sec"),
                "usage": e["meta"].get("usage") or e["meta"].get("usage_metadata"),
                "company": e["meta"].get("company"),
                "grounding_list": e["meta"].get("grounding_list"),
            }
        r.append(d)
    return r


class ChatMessageService:

    async def chat(self, chat_message: ChatMessage) -> ChatResponse:
        context = config.user_info_var.get()

        # add chat context to contextvars
        context["chat_id"] = chat_message.chat_id
        context["project_id"] = chat_message.project_id
        user_id = context["user_id"]

        async def generate_title(cur_message):
            title, _ = await AnyModel().generate_title(cur_message)
            return title

        async def update_title(chat_id, user_message):
            title = await generate_title(user_message)
            await db.chats.update_one(
                {"_id": ObjectId(chat_id)},
                {
                    "$set": {
                        "title": title[:80],
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

        async def persist_conversation(chat_history):
            # if the chat is temporary, do not persist it
            if chat_message.temporary_chat:
                logger.info(
                    f"Temporary chat, not persisting. chat_id: {chat_message.chat_id}"
                )
                return

            chat = (
                await db.chats.find_one({"_id": ObjectId(chat_message.chat_id)})
                if chat_message.chat_id
                else None
            )

            if not chat:
                chat_id_str = chat_message.chat_id or str(ObjectId())
                await db.chats.insert_one(
                    {
                        "_id": ObjectId(chat_id_str),
                        "project_id": ObjectId(chat_message.project_id),
                        "user_id": ObjectId(user_id),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                        "file_context_id": (
                            ObjectId(chat_message.file_context_id)
                            if chat_message.file_context_id
                            else None
                        ),
                        "estimate_total_cost": 0.0,
                        "total_prompt_tokens": 0,
                        "total_completion_tokens": 0,
                        "title": chat_message.title,
                    }
                )
                chat_message.chat_id = chat_id_str

                # start the title generation and update asynchronously
                if not chat_message.title:
                    asyncio.create_task(
                        update_title(chat_message.chat_id, chat_message.message)
                    )
            else:
                chat = await db.chats.find_one({"_id": ObjectId(chat_message.chat_id)})
                if chat.get("title") == "(no name)":
                    asyncio.create_task(
                        update_title(chat_message.chat_id, chat_message.message)
                    )
                await db.chats.update_one(
                    {"_id": ObjectId(chat_message.chat_id)},
                    {"$set": {"updated_at": datetime.now(timezone.utc)}},
                )

            for m in chat_history:
                if m.get("entry_id"):
                    continue
                if not m.get("persist"):
                    continue

                augmented_id = None

                await db.chat_entries.insert_one(
                    {
                        "role": m["role"],
                        "content": m["content"],
                        "created_at": m.get("created_at") or datetime.now(timezone.utc),
                        "is_alternative": m.get("is_alternative", 0),
                        "meta": m.get("meta"),
                        "chat_id": ObjectId(chat_message.chat_id),
                        "user_id": ObjectId(user_id),
                        "project_id": ObjectId(chat_message.project_id),
                        "augmented_message_log_id": augmented_id,
                        "image_url": m.get("image_url"),
                        "file_url": m.get("file_url"),
                        "file_name": m.get("file_name"),
                        "content_type": m.get("content_type"),
                        "output": m.get("output"),
                    }
                )

                meta = m.get("meta")
                if meta and meta.get("estimate_price"):
                    await db.chats.update_one(
                        {"_id": ObjectId(chat_message.chat_id)},
                        {
                            "$inc": {
                                "estimate_total_cost": meta.get("estimate_price"),
                                "total_input_tokens": meta.get("input_tokens", 0),
                                "total_output_tokens": meta.get("output_tokens", 0),
                            }
                        },
                    )

        async def _safe_call_single_llm(
            _chat_history, _model: str | ModelWithParameters
        ):
            if isinstance(_model, ModelWithParameters):
                model_name = _model.name
                _options = _model.model_dump()
            else:
                model_name = _model
                _options = {}

            try:
                _answer, _image_url, files, _meta = await AnyModel().chat(
                    _chat_history,
                    model_name,
                    _options,
                )
                return {
                    "model": model_name,
                    "answer": _answer,
                    "image_url": _image_url,
                    "meta": _meta,
                    "files": files,
                }

            except Exception as e:
                traceback.print_exc()
                return {
                    "model": model_name,
                    "error": e,
                }

        datetime_incrementer = 0

        def get_now():
            nonlocal datetime_incrementer
            datetime_incrementer += 1000
            return (
                datetime.now(timezone.utc) + datetime.resolution * datetime_incrementer
            )

        # -- main body --
        if chat_message.retry_entry_id:
            mode = "retry"
            retry_entry = await db.chat_entries.find_one(
                {"_id": ObjectId(chat_message.retry_entry_id)}
            )
            alternative_counter = await db.chat_entries.count_documents(
                {
                    "created_at": {"$eq": retry_entry.get("created_at")},
                    "chat_id": {"$eq": retry_entry.get("chat_id")},
                }
            )  # first is 0
        else:
            mode = None
            retry_entry = None
            alternative_counter = 0

        # recover the history from the db
        if chat_message.chat_id:
            if mode == "retry":
                cursor = db.chat_entries.find(
                    {
                        "chat_id": ObjectId(chat_message.chat_id),
                        "$or": [
                            {"is_alternative": {"$exists": False}},
                            {"is_alternative": 0},
                        ],
                        "created_at": {"$lt": retry_entry.get("created_at")},
                    }
                ).sort("datetime", 1)
            else:
                cursor = db.chat_entries.find(
                    {
                        "chat_id": ObjectId(chat_message.chat_id),
                        "$or": [
                            {"is_alternative": {"$exists": False}},
                            {"is_alternative": 0},
                        ],
                    }
                ).sort("datetime", 1)

            chat_entries = []
            async for c in cursor:
                chat_entries.append(c)

            chat_history = []
            for c in chat_entries:
                chat_history.append(
                    dict(
                        role=c["role"],
                        content=c["content"],
                        id=c["_id"],
                        image_url=c.get("image_url"),
                        file_url=c.get("file_url"),
                        file_name=c.get("file_name"),
                        content_type=c.get("content_type"),
                    )
                )

                # append generated files also...
                for f in c.get("output") or []:
                    if f.get("type") == OutputTypes.FILE.value:
                        chat_history.append(
                            dict(
                                role=c["role"],
                                id=c["_id"],
                                file_url=f.get("file_url"),
                                file_name=f.get("file_name"),
                                content_type=f.get(
                                    "content_type",
                                    guess_content_type_from_filename(
                                        f.get("file_name")
                                    ),
                                ),
                            )
                        )
        else:
            chat_history = []

        # append the preset content
        if mode == "retry":
            # the last question is already in the history

            if chat_message.file_context_id:

                # recover last message
                last_question = chat_history[-1].get("content")
                chat_history = chat_history[:-1]  # skip last message

                rag_method = VanillaRag.generate_rag_context
                rag_entries = await rag_method(
                    chat_history, last_question, chat_message.file_context_id
                )

                # add as non-persistent
                for c in rag_entries:
                    chat_history.append(
                        dict(
                            role=c["role"],
                            content=c.get("content"),
                            id=None,
                            image_url=c.get("image_url"),
                            file_url=c.get("file_url"),
                            file_name=c.get("file_name"),
                            content_type=c.get("content_type"),
                            persist=False,
                        )
                    )

                # add user question at the and, as non persistent
                chat_history.append(
                    dict(
                        role="user",
                        content=last_question,
                        created_at=get_now(),
                        id=None,
                        persist=False,  # <= already in history
                    )
                )

        else:  # not retry
            if chat_message.preset_list:
                for c in chat_message.preset_list:
                    chat_history.append(
                        dict(
                            role=c["role"],
                            content=c["content"],
                            id=None,
                            image_url=c.get("image_url"),
                            file_url=c.get("file_url"),
                            file_name=c.get("file_name"),
                            content_type=c.get("content_type"),
                            created_at=get_now(),
                            persist=True,
                        )
                    )

            if chat_message.file_context_id:
                rag_method = VanillaRag.generate_rag_context
                # rag_method = RagContextBuilderWithTextSearch.build_context
                rag_entries = await rag_method(
                    chat_history, chat_message.message, chat_message.file_context_id
                )
                # add as non-persistent
                for c in rag_entries:
                    chat_history.append(
                        dict(
                            role=c["role"],
                            content=c.get("content"),
                            id=None,
                            image_url=c.get("image_url"),
                            file_url=c.get("file_url"),
                            file_name=c.get("file_name"),
                            content_type=c.get("content_type"),
                            persist=False,
                        )
                    )

            # append current prompt
            chat_history.append(
                dict(
                    role="user",
                    content=chat_message.message,
                    created_at=get_now(),
                    id=None,
                    persist=True,
                )
            )

        use_created_at = retry_entry["created_at"] if mode == "retry" else get_now()

        # 1 model mode
        if isinstance(chat_message.use_model, str) or len(chat_message.use_model) == 1:
            use_model = (
                chat_message.use_model
                if isinstance(chat_message.use_model, str)
                else chat_message.use_model[0]
            )
            result = await _safe_call_single_llm(chat_history, use_model)
            if "error" in result:
                raise result["error"]

            entry = dict(
                role="assistant",
                content=result.get("answer"),
                image_url=result.get("image_url"),
                output=[],
                created_at=use_created_at,
                persist=True,
                is_alternative=alternative_counter,  # if first, will be 0, if there exists 1, this second will be 1
                meta=(
                    result.get("meta")
                    if isinstance(result.get("meta"), dict)
                    else result.get("meta").model_dump()
                ),
            )
            for f in result.get("files") or []:
                entry["output"].append(
                    {
                        "type": OutputTypes.FILE.value,
                        "file_name": f.get("file_name"),
                        "file_url": f.get("file_url"),
                        "content_type": f.get("content_type"),
                    }
                )
            chat_history.append(entry)

            await persist_conversation(chat_history)
            return ChatResponse(
                response=result.get("answer"),
                chat_id=chat_message.chat_id,
            )

        else:  # multi chat mode
            print("multi chat mode: ", chat_message.use_model)
            print("chat history: -------\n", chat_history, "\n-----------------\n")
            results: List[Any] = []
            async with asyncio.TaskGroup() as tg:
                tasks = {
                    tg.create_task(_safe_call_single_llm(chat_history, m)): m
                    for m in chat_message.use_model
                }

            errors = []
            for task, model in tasks.items():
                try:
                    result = task.result()
                    if "error" in result:
                        print(f"Error with model {model}, error: {result.get('error')}")
                        errors.append(f"[{model.name}] {result.get('error')}")
                    else:
                        results.append({**result})
                except Exception as e:
                    print(f"Error with model {model}, error: {str(e)}")
                    errors.append(f"[{model.name}] {str(e)}")
                    traceback.print_exc()

            for index, r in enumerate(results):
                # the first is the main, others are alternative
                entry = dict(
                    role="assistant",
                    content=r["answer"],
                    image_url=r["image_url"],
                    output=[],
                    persist=True,
                    is_alternative=alternative_counter + index,
                    created_at=use_created_at,
                    meta=(
                        r["meta"]
                        if isinstance(r["meta"], dict)
                        else r["meta"].model_dump()
                    ),
                )
                for f in r.get("files") or []:
                    entry["output"].append(
                        {
                            "type": OutputTypes.FILE.value,
                            "file_name": f.get("file_name"),
                            "file_url": f.get("file_url"),
                            "content_type": f.get("content_type"),
                        }
                    )
                chat_history.append(entry)

            errors = "Some models have errors. " + "\n".join(errors) if errors else None
            await persist_conversation(chat_history)
            return ChatResponse(
                response=[r.get("answer") or r.get("image_url") for r in results],
                chat_id=chat_message.chat_id,
                errors=errors,
            )

    async def chat_next(self, args: ChatMessageNext) -> ChatResponse:
        """
        Execute the same query, but using the next offset page of the content
        """

        # recover the last user message
        message_entry = await db.chat_entries.find_one(
            {"_id": ObjectId(args.entry_id), "role": "user"},
            sort=[("created_at", DESCENDING)],
        )

        if not message_entry:
            raise HTTPException(
                detail="Invalid chat entry id", status_code=status.HTTP_400_BAD_REQUEST
            )

        # get augmented message
        if not message_entry.get("augmented_message_log_id"):
            raise HTTPException(
                detail="Invalid chat entry id", status_code=status.HTTP_400_BAD_REQUEST
            )

        augmented = await db.augmented_message_log.find_one(
            {"_id": message_entry.get("augmented_message_log_id")}
        )
        if not augmented:
            raise HTTPException(
                detail="Invalid chat entry id", status_code=status.HTTP_400_BAD_REQUEST
            )

        params = ChatMessage(
            use_sliding_window=args.use_sliding_window,
            message=message_entry.get("content"),
            chat_id=str(message_entry.get("chat_id")),
            project_id=str(message_entry.get("project_id")),
        )
        return await self.chat(params)


async def main():
    r = await ChatMessageService().chat(
        ChatMessage(
            message="Hello!",
            system_message="64f895380247e447fe670a1c",
            project_id="64f1d62a3492d2decaba34f3",
            chat_id="64f8cea367780fd2daaa0165",
            user_id="64f21bf56a8609c6dcc94cd1",
        )
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
