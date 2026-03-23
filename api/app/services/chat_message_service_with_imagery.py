import asyncio
import json
import traceback
from datetime import datetime, timezone

from bson import ObjectId

from app.services.imagery.reason_with_imagery import ImageryReasoner
from app.utils.file_utils import guess_content_type_from_filename, CustomJSONEncoder
from .imagery_all.imagery_tools_backed_reasoner_mental_rotation_2 import (
    ToolsBackedImageryReasoner_MentalRotation2,
)
from .imagery_all.imagery_tools_backed_reasoner_mental_rotation_3 import (
    ToolsBackedImageryReasoner_MentalRotation3_WithFullHistoryToReasoning,
)
from .imagery_with_tools.tools_backed_imagery_reasoner import ToolsBackedImageryReasoner
from .imagery_with_tools__mental_rotation_1.tools_backed_imagery_reasoner import (
    ToolsBackedImageryReasoner_MentalRotation1,
)
from .imagery_with_tools_incremental.incremental_tools_backed_imagery_reasoner import (
    IncrementalToolsBackedImageryReasoner,
)
from ..config.config import config
from ..database_async import db_async as db  # <-- use async DB
from ..llm_services.any_model import AnyModel
from ..models.chat_message import (
    ChatMessage,
    ChatResponse,
    OutputTypes,
    ModelWithParameters,
)


class ChatMessageServiceWithImagery:

    async def chat(self, chat_message: ChatMessage):
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
                        "title": "",
                    }
                )
                chat_message.chat_id = chat_id_str

                # start the title generation and update asynchronously
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

        # async def _safe_call_single_llm(_chat_history, _model: str | ModelWithParameters):
        #     if isinstance(_model, ModelWithParameters):
        #         model_name = _model.name
        #         _options = _model.model_dump()
        #     else:
        #         model_name = _model
        #         _options = {}
        #
        #     try:
        #         _answer, _image_url, files, _meta = await AnyModel().chat(
        #             _chat_history,
        #             model_name,
        #             _options,
        #         )
        #         return {
        #             "model": model_name,
        #             "answer": _answer,
        #             "image_url": _image_url,
        #             "meta": _meta,
        #             "files": files,
        #         }
        #
        #     except Exception as e:
        #         traceback.print_exc()
        #         return {
        #             "model": model_name,
        #             "error": e,
        #         }

        def get_now():
            nonlocal datetime_incrementer
            datetime_incrementer += 1000
            return (
                datetime.now(timezone.utc) + datetime.resolution * datetime_incrementer
            )

        # -- main body --
        datetime_incrementer = 0
        mode = None
        retry_entry = None
        alternative_counter = 0

        # recover the history from the db
        # if chat_message.chat_id:
        #     raise Exception('Imagery not support continuation yet')
        #     cursor = db.chat_entries.find(
        #         {
        #             "chat_id": ObjectId(chat_message.chat_id),
        #             "$or": [
        #                 {"is_alternative": {"$exists": False}},
        #                 {"is_alternative": 0},
        #             ],
        #         }
        #     ).sort("datetime", 1)

        #     chat_entries = []
        #     async for c in cursor:
        #         chat_entries.append(c)

        #     chat_history = []
        #     for c in chat_entries:
        #         chat_history.append(
        #             dict(
        #                 role=c["role"],
        #                 content=c["content"],
        #                 id=c["_id"],
        #                 image_url=c.get("image_url"),
        #                 file_url=c.get("file_url"),
        #                 file_name=c.get("file_name"),
        #                 content_type=c.get("content_type"),
        #             )
        #         )

        #         # append generated files also...
        #         for f in (c.get("output") or []):
        #             if f.get("type") == OutputTypes.FILE.value:
        #                 chat_history.append(
        #                     dict(
        #                         role=c["role"],
        #                         id=c["_id"],
        #                         file_url=f.get("file_url"),
        #                         file_name=f.get("file_name"),
        #                         content_type=f.get(
        #                             "content_type", guess_content_type_from_filename(f.get("file_name"))
        #                         ),
        #                     )
        #                 )
        # else:
        chat_history = []

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
        prompt = chat_message.message

        use_model = (
            chat_message.use_model
            if isinstance(chat_message.use_model, str)
            else chat_message.use_model[0]
        )
        print("\n*** UseModel **=> ", use_model)

        save_raw = True
        chat_history_len = len(chat_history)

        reasoner_by_model = {
            "imagery": ImageryReasoner,
            "tools-based-imagery": ToolsBackedImageryReasoner,
            "tools-based-imagery--mental-rotation-1": ToolsBackedImageryReasoner_MentalRotation1,
            "incremental-tools-based-imagery": IncrementalToolsBackedImageryReasoner,
            "tools-based-imagery--mental-rotation-2": ToolsBackedImageryReasoner_MentalRotation2,
            "tools-based-imagery--mental-rotation-3": ToolsBackedImageryReasoner_MentalRotation3_WithFullHistoryToReasoning,
        }
        answer, chat_history, iter_steps = await reasoner_by_model[
            use_model.name
        ]().reason_loop(chat_history, use_model, options=None, save_raw=save_raw)

        # print('\n\n-----------------------\nReceived history: ',
        #       json.dumps(chat_history[chat_history_len:], indent=2, cls=CustomJSONEncoder))

        if not save_raw:
            entry = dict(
                role="assistant",
                content=answer,
                image_url=None,
                output=[],
                created_at=use_created_at,
                persist=True,
                is_alternative=alternative_counter,  # if first, will be 0, if there exists 1, this second will be 1
                meta=None,
                imagery_steps=iter_steps,
            )
            chat_history.append(entry)

        await persist_conversation(chat_history)
        return ChatResponse(
            response=answer,
            chat_id=chat_message.chat_id,
        )
