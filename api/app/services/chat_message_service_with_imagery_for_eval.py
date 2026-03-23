import asyncio
import json
import traceback
from datetime import datetime, timezone

from bson import ObjectId

from app.services.imagery_all.imagery_tools_backed_reasoner_eval_3 import (
    ToolsBackedImageryReasoner_Eval3,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_4 import (
    ToolsBackedImageryReasoner_Eval4,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_5 import (
    ToolsBackedImageryReasoner_Eval5,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_6 import (
    ToolsBackedImageryReasoner_Eval6,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_7 import (
    ToolsBackedImageryReasoner_Eval7,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_8 import (
    ToolsBackedImageryReasoner_Eval8,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_9 import (
    ToolsBackedImageryReasoner_Eval9,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_9_1_sem_reset import (
    ToolsBackedImageryReasoner_Eval9_1,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_90 import (
    ToolsBackedImageryReasoner_Eval90,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_91_prompt_ablation import (
    ToolsBackedImageryReasoner_Eval91,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_92_prompt_with_cot import (
    ToolsBackedImageryReasoner_Eval92,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_93 import (
    ToolsBackedImageryReasoner_Eval93,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_94 import (
    ToolsBackedImageryReasoner_Eval94,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_95 import (
    ToolsBackedImageryReasoner_Eval95,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_96 import (
    ToolsBackedImageryReasoner_Eval96,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05009 import (
    ToolsBackedImageryReasoner_Eval_05009,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05094 import (
    ToolsBackedImageryReasoner_Eval_05094,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05095 import (
    ToolsBackedImageryReasoner_Eval_05095,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05096 import (
    ToolsBackedImageryReasoner_Eval_05096,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05097 import (
    ToolsBackedImageryReasoner_Eval_05097,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05097_1_gpt import (
    ToolsBackedImageryReasoner_Eval_05097_1,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05097_2_gemini import (
    ToolsBackedImageryReasoner_Eval_05097_2,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05097_3_claude import (
    ToolsBackedImageryReasoner_Eval_05097_3,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_05098 import (
    ToolsBackedImageryReasoner_Eval_05098,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_07099 import (
    ToolsBackedImageryReasoner_Eval_07099,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_07099_prompt1 import (
    ToolsBackedImageryReasoner_Eval_07099_Prompt1,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_07099_prompt2 import (
    ToolsBackedImageryReasoner_Eval_07099_Prompt2,
)
from app.services.imagery_all.imagery_tools_backed_reasoner_eval_07099_prompt3 import (
    ToolsBackedImageryReasoner_Eval_07099_Prompt3,
)
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


class ChatMessageServiceWithImageryForEval:

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
            "tools-based-imagery--eval-3": ToolsBackedImageryReasoner_Eval3,
            "tools-based-imagery--eval-4": ToolsBackedImageryReasoner_Eval4,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-5": ToolsBackedImageryReasoner_Eval5,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-6": ToolsBackedImageryReasoner_Eval6,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-7": ToolsBackedImageryReasoner_Eval7,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-8": ToolsBackedImageryReasoner_Eval8,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-9": ToolsBackedImageryReasoner_Eval9,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-90": ToolsBackedImageryReasoner_Eval90,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-91": ToolsBackedImageryReasoner_Eval91,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-92": ToolsBackedImageryReasoner_Eval92,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-93": ToolsBackedImageryReasoner_Eval93,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-94": ToolsBackedImageryReasoner_Eval94,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-95": ToolsBackedImageryReasoner_Eval95,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-96": ToolsBackedImageryReasoner_Eval96,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05009": ToolsBackedImageryReasoner_Eval_05009,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05094": ToolsBackedImageryReasoner_Eval_05094,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05095": ToolsBackedImageryReasoner_Eval_05095,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05096": ToolsBackedImageryReasoner_Eval_05096,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05097": ToolsBackedImageryReasoner_Eval_05097,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05097_1": ToolsBackedImageryReasoner_Eval_05097_1,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05097_2": ToolsBackedImageryReasoner_Eval_05097_2,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05097_3": ToolsBackedImageryReasoner_Eval_05097_3,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-05098": ToolsBackedImageryReasoner_Eval_05098,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-07099": ToolsBackedImageryReasoner_Eval_07099,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-07099_prompt1": ToolsBackedImageryReasoner_Eval_07099_Prompt1,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-07099_prompt2": ToolsBackedImageryReasoner_Eval_07099_Prompt2,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-07099_prompt3": ToolsBackedImageryReasoner_Eval_07099_Prompt3,  # pyright: ignore[reportUndefinedVariable]
            "tools-based-imagery--eval-9_1": ToolsBackedImageryReasoner_Eval9_1,  # pyright: ignore[reportUndefinedVariable]
        }
        answer, chat_history, iter_steps = await reasoner_by_model[
            use_model.name
        ]().reason_loop(chat_message, use_model, options=None, save_raw=save_raw)

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
