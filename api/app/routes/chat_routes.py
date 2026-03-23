# routes/chat_routes.py
from typing import List

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from starlette import status
from starlette.responses import JSONResponse

from app.config.config import config
from app.services.chat_service_async import ChatServiceAsync
from ..models.chat import ChatBase, ChatInDB, ChatWithContent, ChatEntriesForSelection
from ..services.chat_service import ChatService

router = APIRouter()


class InitNewRequest(BaseModel):
    project_id: str


@router.get("/chats/get-new")
def get_new():
    return {"chat_id": ChatService.get_new_id()}


@router.post("/chats", response_model=ChatInDB)
def create_chat(chat: ChatBase):
    return ChatService.create_chat(chat)


@router.get("/chats/search/fulltext", response_model=list[ChatWithContent])
async def get_latest_chats_with_intro_2(
    project_id: str, q: str = None, selected_chat_id: str = None, last_id: str = None
):
    # if q:
    return await ChatServiceAsync.search_chat(project_id, q)


@router.get("/chats/search/titles", response_model=dict)
async def get_latest_chats_with_intro(
    project_id: str | None = config.default_project_id,
    q: str = None,
    selected_chat_id: str = None,
    last_id: str = None,
    is_bookmarked: bool = False,
    file_context_id: str = None,
):
    return await ChatServiceAsync.search_chat_titles_async(
        project_id, q, last_id, is_bookmarked, selected_chat_id, file_context_id
    )


@router.get("/chats/search/public", response_model=list[dict])
def get_recent_public_chats():
    return ChatService.search_recent_public_chats()


@router.get("/chats/{chat_id}", response_model=ChatInDB)
def get_chat_by_id(chat_id: str):
    chat = ChatService.get_chat_by_id(chat_id)
    if chat:
        return chat
    else:
        raise HTTPException(status_code=404, detail="Chat not found")


class SelectiveDuplicateRequest(BaseModel):
    title: str
    entries: List[str]


@router.post("/chats/{chat_id}/selective-duplicate")
def selective_duplicate_chat(chat_id: str, args: SelectiveDuplicateRequest):
    new_chat_id = ChatService.selective_duplicate(chat_id, args.title, args.entries)
    return Response(status_code=200, content=new_chat_id)


class NewTitle(BaseModel):
    title: str


@router.put("/chats/{chat_id}/rename")
def rename_chat(chat_id: str, arg: NewTitle):
    ChatService.rename(chat_id, arg.title)
    return Response(status_code=200)


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    await ChatService.delete(chat_id)
    return Response(status_code=200)


@router.delete("/chats/{chat_id}/entry/{entry_id}")
async def delete_entry(chat_id: str, entry_id: str):
    await ChatService.delete_entry(chat_id, entry_id)
    return Response(status_code=200)


@router.put("/chats/{chat_id}/entry/{entry_id}/make-alternative-main")
async def make_alternative_main(chat_id: str, entry_id: str):
    await ChatService.make_alternative_main(chat_id, entry_id)
    return Response(status_code=200)


@router.get("/chats/{chat_id}/thread")
async def get_chat_thread(chat_id: str, skip: int):
    return await ChatServiceAsync.get_chat_thread_async(chat_id, skip)

@router.get("/chats/{chat_id}/thread-public", response_model=dict)
def get_chat_thread(chat_id: str):
    return ChatService.get_chat_thread_public(chat_id)


@router.put("/chats/{chat_id}/make_shared")
def make_shared(chat_id: str):
    shared_id = ChatService.make_shared(chat_id)
    return JSONResponse(
        content={"shared_id": shared_id}, status_code=status.HTTP_200_OK
    )


@router.put("/chats/{chat_id}/public")
def toggle_public(chat_id: str):
    return ChatService.toggle_public(chat_id)
