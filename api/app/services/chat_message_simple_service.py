import json

from ..llm_services.any_model import AnyModel
from ..models.chat_message import ChatSimpleResponse, ChatSimpleMessage


class ChatMessageSimpleService:

    @staticmethod
    async def chat_simple_call(arg: ChatSimpleMessage) -> ChatSimpleResponse:
        answer, meta = await AnyModel.simple_chat_call(
            arg.system_message,
            arg.message,
            arg.use_model,
            arg.image_url,
            # arg.temperature
        )
        return ChatSimpleResponse(
            response=answer
            # meta=json.dumps(meta)
        )
