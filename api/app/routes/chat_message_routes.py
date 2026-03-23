import traceback

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.language_models.imagery_eval_models import ImageryEvalModel
from app.services.chat_message_service_with_imagery_for_eval import (
    ChatMessageServiceWithImageryForEval,
)

from ..language_models.imagery_fake_models import ImageryFakeModel
from ..services.chat_message_service_with_imagery import ChatMessageServiceWithImagery
from ..services.chat_message_simple_service import ChatMessageSimpleService
from ..services.chat_message_service import ChatMessageService
from ..models.chat_message import (
    ChatResponse,
    ChatMessage,
    ChatMessageNext,
    ChatSimpleResponse,
    ChatSimpleMessage,
    BranchInNewChatParams,
)
import logging

from ..services.chat_service_async import ChatServiceAsync
from ..services.imagery_with_tools_incremental.incremental_tools_backed_imagery_reasoner import (
    IncrementalToolsBackedImageryReasoner,
)

router = APIRouter()

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize ChatMessageService
# chat_service = ChatMessageService()
chat_service = ChatMessageServiceWithImagery()


@router.post("/chat/message")
async def create_chat_message(request: Request, chat_message: ChatMessage):

    model = chat_message.use_model[0].name
    if ImageryFakeModel.is_imagery_model(model):
        return await ChatMessageServiceWithImagery().chat(chat_message)
    elif ImageryEvalModel.is_imagery_eval_model(model):
        return await ChatMessageServiceWithImageryForEval().chat(chat_message)
    else:
        return await ChatMessageService().chat(chat_message)


@router.post("/chat/message/branch-in-new-chat")
async def create_chat_message_fork(request: Request, args: BranchInNewChatParams):
    response = await ChatServiceAsync.duplicate_until_assistant_entry_id(
        args.chat_id, args.entry_id
    )
    return response


@router.post("/chat/message/simple", response_model=ChatSimpleResponse)
async def chat_simple_message(arg: ChatSimpleMessage):
    logger.info(f"Request data: {arg}")
    return await ChatMessageSimpleService.chat_simple_call(arg)


