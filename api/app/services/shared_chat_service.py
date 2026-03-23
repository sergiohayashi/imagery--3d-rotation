# services/chat_service.py
import asyncio
import collections
from typing import List
from uuid import uuid4

from bson import ObjectId, Regex
from fastapi import HTTPException
from pymongo import DESCENDING
from starlette import status

from ..models.chat import ChatSharedListItem
from ..database import db
from ..config.config import config
from datetime import datetime


class SharedChatService:

    @staticmethod
    def get_shared_list(project_id: str) -> List[ChatSharedListItem]:
        user_id = config.user_info_var.get().get("user_id")
        # Query to find chats with expired shared_id_expire_date for a given user_id
        query = {
            "user_id": ObjectId(user_id),
            "project_id": ObjectId(project_id),
            "shared_id_expire_date": {"$exists": True, "$gte": datetime.now()},
        }

        # Execute the query
        shared_chats = list(db.chats.find(query))
        result = []
        for chat in shared_chats:
            result.append(
                ChatSharedListItem(
                    shared_id=chat.get("shared_id"),
                    title=chat.get("title"),
                    shared_id_expire_date=chat.get("shared_id_expire_date"),
                )
            )
        return result

    @staticmethod
    def remove_shared(shared_id):
        user_id = config.user_info_var.get().get("user_id")
        chat = db.chats.find_one({"shared_id": shared_id, "user_id": ObjectId(user_id)})
        if not chat:
            raise HTTPException(
                detail="Invalid ID", status_code=status.HTTP_400_BAD_REQUEST
            )

        update_query = {
            "$unset": {
                "shared_id": "",  # The value is ignored when using $unset
                "shared_id_expire_date": "",  # The value is ignored when using $unset
            }
        }
        db.chats.update_one({"_id": chat["_id"]}, update_query)
