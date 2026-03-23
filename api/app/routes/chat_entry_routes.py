# routes/chat_entry_routes.py
from fastapi import APIRouter, HTTPException, Response
from ..models.chat_entry import ChatEntryBase, ChatEntryInDB
from ..services.chat_entry_service import ChatEntryService

router = APIRouter()


@router.post("/chat_entries", response_model=ChatEntryInDB)
def create_chat_entry(chat_entry: ChatEntryBase):
    ChatEntryService.create_chat_entry(chat_entry)
    return Response(status_code=200)


@router.get("/chat_entries/{chat_id}", response_model=list[ChatEntryInDB])
def get_chat_entry(chat_id: str):
    return ChatEntryService.get_chat_entry(chat_id)


@router.get("/chat_entries", response_model=list[ChatEntryInDB])
def get_all_chat_entries():
    return ChatEntryService.get_all_chat_entries()


@router.get("/chat_entries/{chat_entry_id}", response_model=ChatEntryInDB)
def get_chat_entry_by_id(chat_entry_id: str):
    chat_entry = ChatEntryService.get_chat_entry_by_id(chat_entry_id)
    if chat_entry:
        return chat_entry
    else:
        raise HTTPException(status_code=404, detail="Chat entry not found")
