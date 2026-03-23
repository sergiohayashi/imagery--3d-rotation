# services/system_message_service.py
from datetime import datetime

from ..database import db
from bson import ObjectId, Regex
from ..config.config import config


class BookmarkService:

    @staticmethod
    def set_bookmark(chat_id: str):
        user_id = config.user_info_var.get()["user_id"]
        existing = db.bookmarks.find_one(
            {"user_id": ObjectId(user_id), "chat_id": ObjectId(chat_id)}
        )
        if existing is not None:
            inserted = db.bookmarks.insert_one(
                {
                    "user_id": ObjectId(user_id),
                    "chat_id": ObjectId(chat_id),
                    "created_at": datetime.now(),
                }
            )
            return {"id": str(inserted.inserted_id)}
        else:
            return {"id": str(existing["_id"])}

    @staticmethod
    def remove_bookmark(chat_id: str):
        user_id = config.user_info_var.get()["user_id"]
        db.system_messages.delete_one(
            {"chat_id": ObjectId(user_id), "user_id": ObjectId(chat_id)}
        )

    @staticmethod
    def get_bookmark_for(user_id: str, chat_id: str) -> bool:
        obj = db.bookmarks.find_one(
            {"user_id": ObjectId(user_id), "chat_id": ObjectId(chat_id)}
        )
        return obj is not None

    @staticmethod
    def toggle(chat_id):
        user_id = config.user_info_var.get()["user_id"]
        existing = db.bookmarks.find_one(
            {"user_id": ObjectId(user_id), "chat_id": ObjectId(chat_id)}
        )
        if existing is None:
            db.bookmarks.insert_one(
                {
                    "user_id": ObjectId(user_id),
                    "chat_id": ObjectId(chat_id),
                    "created_at": datetime.now(),
                }
            )
        else:
            db.bookmarks.delete_one(
                {"chat_id": ObjectId(chat_id), "user_id": ObjectId(user_id)}
            )
        return BookmarkService.get_bookmark_for(user_id, chat_id)
