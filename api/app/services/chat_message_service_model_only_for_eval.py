from datetime import datetime, timezone
import json

from bson import ObjectId

from app.utils.file_utils import CustomJSONEncoder

from ..config.config import config
from ..database_async import db_async as db  # <-- use async DB
from ..llm_services.any_model import AnyModel
from ..models.chat_message import (
    ChatMessage,
    ChatResponse,
)

system_prompt = """
You are solving a visual reasoning puzzle.

**Input:**
1. A **2D perspective image** of an **Original** 3D block model.
2. Three alternative models labeled **A**, **B**, and **C**.
**Objective:** Identify which alternative (**A**, **B**, or **C**) does **NOT** correspond to the same 3D structure as the **Original** model (i.e., find the "odd one out").

**Output:**
As output, generate only the letter of you answer. A single character output (e.g., "A", "B", "C") is expected. Nothing else.

"""


class ChatMessageServiceModelOnlyForEval:

    async def evaluate(self, chat_messsage: ChatMessage):
        response = await self.chat(chat_messsage)
        return response.response

    async def chat(self, chat_message: ChatMessage) -> ChatResponse:
        context = config.user_info_var.get()

        # add chat context to contextvars
        context["chat_id"] = chat_message.chat_id
        context["project_id"] = chat_message.project_id
        user_id = context["user_id"]

        async def persist_conversation(chat_history):
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
            for m in chat_history:
                if m.get("entry_id"):
                    continue
                if not m.get("persist"):
                    continue

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

        use_model = (
            chat_message.use_model
            if isinstance(chat_message.use_model, str)
            else chat_message.use_model[0]
        )
        print("\n*** UseModel **=> ", use_model.name)
        assert use_model, f"Model nof provided!"

        chat_history = [
            dict(
                role="system",
                content=system_prompt,
            ),
            # problem image
            dict(
                role="user",
                file_url=chat_message.imagery_args["question_image_url"],
                file_name=chat_message.imagery_args["question_file_name"],
                content_type="image/png",
                created_at=get_now(),
                id=None,
                persist=True,
            ),
            # question
            dict(
                role="user",
                content=chat_message.message,
                created_at=get_now(),
                id=None,
                persist=True,
            ),
        ]
        print(
            f"\n------------------------->>>\ncall_llm {use_model.name}:>>>",
            json.dumps(chat_history, indent=2, cls=CustomJSONEncoder),
        )
        answer, _, _, meta = await AnyModel().chat(chat_history, use_model.name, None)
        # remove double quotes from answer
        answer = answer.replace('"', "")
        print(
            f"\n-------------------------<<<\ncall_llm {use_model.name}:<<<",
            f"answer: [{answer}]",
        )

        # answer
        entry = dict(
            role="assistant",
            content=answer,
            created_at=get_now(),
            persist=True,
            meta=meta,
        )
        chat_history.append(entry)

        await persist_conversation(chat_history)
        return ChatResponse(
            response=answer,
            chat_id=chat_message.chat_id,
        )
