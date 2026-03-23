# services/user_service.py
from datetime import datetime
import random
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import DESCENDING

from ..llm_services.any_model import AnyModel
from ..database import db
from ..config.config import config


class DiscoverService:

    @staticmethod
    async def get_suggestion():
        user_id = config.user_info_var.get().get("user_id")
        if not user_id:
            raise HTTPException(
                detail="Invalid user or without permission",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # get user last N chat titles
        # find in title
        N = 250
        random_selection_count = 41
        chats_cursor = (
            db.chats.find(
                {
                    "user_id": ObjectId(user_id),
                },
                {
                    "_id": 0,  # Exclude the _id field
                    "title": 1,  # Include the title field
                },
            )
            .sort("created_at", DESCENDING)
            .limit(N)
        )
        chats = list(chats_cursor)
        random_chats = random.sample(chats, min(random_selection_count, len(chats)))

        chats_titles = [chat["title"] for chat in random_chats]

        # get suggestion
        suggestion, _ = await AnyModel().generate_suggestion_v2(chats_titles)

        # save to database
        db.discover.insert_one(
            {
                "user_id": ObjectId(user_id),
                "created_at": datetime.now(),
                "suggestion": suggestion,
            }
        )

        return suggestion

    @staticmethod
    async def get_latest_suggestion():
        user_id = config.user_info_var.get()["user_id"]

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        query = {"user_id": ObjectId(user_id), "created_at": {"$gte": today}}
        result = list(db.discover.find(query).sort("created_at", -1).limit(1))
        return result[0]["suggestion"] if len(result) > 0 else None
