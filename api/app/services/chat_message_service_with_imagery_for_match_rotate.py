import asyncio
import json
import traceback
from datetime import datetime, timezone

from bson import ObjectId

from app.services.imagery_all.imagery_tools_backed_reasoner__match_by_rotation_0101 import (
    ToolsBaseImageryMatchByRotation00101,
)
from app.services.imagery_all.imagery_tools_backed_reasoner__match_by_rotation_0102 import (
    ToolsBaseImageryMatchByRotation00102,
)

from app.utils.file_utils import guess_content_type_from_filename, CustomJSONEncoder
from ..config.config import config
from ..database_async import db_async as db  # <-- use async DB
from ..llm_services.any_model import AnyModel
from ..models.chat_message import (
    ChatMessage,
    ChatResponse,
    OutputTypes,
    ModelWithParameters,
)


class ChatMessageServiceWithImageryForMatchRotate:

    async def evaluate(self, chat_messsage: ChatMessage):
        response = await self.chat(chat_messsage)
        return response.response

    async def chat(self, chat_message: ChatMessage) -> ChatResponse:
        context = config.user_info_var.get()

        # add chat context to contextvars
        context["chat_id"] = chat_message.chat_id
        context["project_id"] = chat_message.project_id
        user_id = context["user_id"]

        async def persist_conversation(chat_history, prompt, reasoner_model):
            # if not chat:
            # eval mode is always new chat
            chat_id_str = chat_message.chat_id or str(ObjectId())
            await db.chats.insert_one(
                {
                    "_id": ObjectId(chat_id_str),
                    "project_id": ObjectId(chat_message.project_id),
                    "user_id": ObjectId(user_id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    # "file_context_id": (
                    #     ObjectId(chat_message.file_context_id)
                    #     if chat_message.file_context_id
                    #     else None
                    # ),
                    "estimate_total_cost": 0.0,
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "title": chat_message.title,
                    "prompt": prompt,
                    "reasoner_model": reasoner_model,
                }
            )
            chat_message.chat_id = chat_id_str
            for m in chat_history:
                if m.get("entry_id"):
                    continue
                if not m.get("persist"):
                    continue

                augmented_id = None

                await db.chat_entries.insert_one(
                    {
                        "role": m["role"],
                        "content": m.get("content"),
                        "created_at": m.get("created_at") or datetime.now(timezone.utc),
                        "is_alternative": m.get("is_alternative", 0),
                        "meta": m.get("meta"),
                        "chat_id": ObjectId(chat_message.chat_id),
                        "user_id": ObjectId(user_id),
                        "project_id": ObjectId(chat_message.project_id),
                        # "augmented_message_log_id": augmented_id,
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

        use_created_at = retry_entry["created_at"] if mode == "retry" else get_now()
        # prompt = chat_message.message

        use_model = (
            chat_message.use_model
            if isinstance(chat_message.use_model, str)
            else chat_message.use_model[0]
        )
        # print('\n*** UseModel **=> ', use_model)

        save_raw = True
        # chat_history_len = len(chat_history)

        reasoner_by_model = {
            "tools-based-imagery--match-by-rotation-00101": ToolsBaseImageryMatchByRotation00101,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--match-by-rotation-00102": ToolsBaseImageryMatchByRotation00102,  # pyright: ignore[reportUndefinedVariable]
            # "tools-based-imagery--eval-08101_prompt5": ToolsBackedImageryReasoner_Eval_08101_Prompt5,  # pyright: ignore[reportUndefinedVariable]
        }
        answer, chat_history, iter_steps = await reasoner_by_model[
            use_model.name
        ]().reason_loop(chat_message, use_model, options=None, save_raw=save_raw)

        # print('\n\n-----------------------\nReceived history: ',
        #       json.dumps(chat_history[chat_history_len:], indent=2, cls=CustomJSONEncoder))

        prompt = (
            reasoner_by_model[use_model.name].prompt
            if hasattr(reasoner_by_model[use_model.name], "prompt")
            else None
        )
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

        await persist_conversation(chat_history, prompt, use_model.name)
        return ChatResponse(
            response=answer,
            chat_id=chat_message.chat_id,
        )
