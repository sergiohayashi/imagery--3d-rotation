# services/user_service.py
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from ..database import db
from .usage_log_service import UsageLogService
from app.services.usage_log_service_async import UsageLogServiceAsync
from ..config.config import config


class AccountService:

    @staticmethod
    def get_current_balance():
        user_id = config.user_info_var.get().get("user_id")
        if not user_id:
            raise HTTPException(
                detail="Invalid user or without permission",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return UsageLogService.get_current_usage(user_id)

    @staticmethod
    def switch_exclude_from_ranking():
        user_id = config.user_info_var.get().get("user_id")
        if not user_id:
            raise HTTPException(
                detail="Invalid user or without permission",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        collection = db.users
        user = collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                detail="User not found", status_code=status.HTTP_400_BAD_REQUEST
            )

        _status = not user.get("exclude_from_ranking", False)
        collection.update_one(
            {
                "_id": user["_id"],
            },
            {"$set": {"exclude_from_ranking": _status}},
        )
        return {"status": _status}

    @staticmethod
    def get_exclude_from_ranking():
        user_id = config.user_info_var.get().get("user_id")
        if not user_id:
            raise HTTPException(
                detail="Invalid user or without permission",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        collection = db.users
        user = collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                detail="User not found", status_code=status.HTTP_400_BAD_REQUEST
            )

        _status = user.get("exclude_from_ranking", False)
        return {"status": _status}
