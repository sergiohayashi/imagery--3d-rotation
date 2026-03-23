from typing import List

from fastapi import APIRouter, HTTPException, Response
from ..services.public_shared_chat_service import PublicSharedChatService
from ..services.shared_chat_service import SharedChatService

router = APIRouter()


@router.get("/public/shared_chats/{shared_id}/thread")
def get_chat_thread(shared_id: str):
    return PublicSharedChatService.get_chat_thread(shared_id)


@router.get("/shared_chats")
def get_chat_thread(project_id: str):
    return SharedChatService.get_shared_list(project_id)


@router.delete("/shared_chats/{shared_id}")
def remove_shared(shared_id: str):
    return SharedChatService.remove_shared(shared_id)
