# services/chat_entry_service.py
from datetime import datetime

from bson import ObjectId

from ..models.chat import ChatBase
from .chat_service import ChatService
from ..models.chat_entry import ChatEntryBase, ChatEntryInDB
from ..database import db


class ChatEntryService:
    @staticmethod
    def create_chat_entry(chat_entry: ChatEntryBase) -> ChatEntryInDB:
        chat_entry_dict = chat_entry.model_dump(by_alias=True)

        # Check if 'chat' field is provided
        if not chat_entry_dict.get("chat"):
            # If not, create a new 'Chat' record
            new_chat = ChatBase(
                user=ObjectId(chat_entry_dict["user"]),
                project=ObjectId(chat_entry_dict["project"]),
            )
            created_chat = ChatService.create_chat(new_chat)
            chat_entry_dict["chat"] = created_chat.id

        chat_entry_dict["chat"] = ObjectId(chat_entry_dict["chat"])
        chat_entry_dict["datetime"] = datetime.now()
        chat_entry_id = db.chat_entries.insert_one(chat_entry_dict).inserted_id
        return ChatEntryInDB(**db.chat_entries.find_one({"_id": chat_entry_id}))

    @staticmethod
    def get_chat_entry(chat_id: str) -> list[ChatEntryInDB]:
        chat_entries = db.chat_entries.find({"chat": chat_id}).sort("timestamp", 1)
        return [ChatEntryInDB(**chat_entry) for chat_entry in chat_entries]

    @staticmethod
    def get_all_chat_entries() -> list[ChatEntryInDB]:
        chat_entries = db.chat_entries.find()
        return [ChatEntryInDB(**chat_entry) for chat_entry in chat_entries]

    @staticmethod
    def get_chat_entry_by_id(chat_entry_id: str) -> ChatEntryInDB:
        chat_entry = db.chat_entries.find_one({"_id": chat_entry_id})
        if chat_entry:
            return ChatEntryInDB(**chat_entry)
        else:
            return None
