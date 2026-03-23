from datetime import datetime

from pymongo import DESCENDING

from .user_service import UserService
from ..models.feedback import PostFeedbackRequest

from ..config.config import config
from bson import ObjectId
from ..database import db


class FeedbackService:

    @staticmethod
    def create_feedback(request: PostFeedbackRequest) -> str:
        user_info = config.user_info_var.get()

        # insert
        inserted = db.feedbacks.insert_one(
            {
                "created_at": datetime.now(),
                "user_id": ObjectId(user_info.get("user_id")),
                "text": request.text,
                "category": request.category,
                "attachment_files": request.attachment_files,
            }
        )
        return str(inserted.inserted_id)

    @classmethod
    def get_all_for_user(cls):
        user_info = config.user_info_var.get()

        feedbacks = db.feedbacks.find(
            {"user_id": ObjectId(user_info.get("user_id"))},
            sort=[("created_at", DESCENDING)],
        )

        results = []
        cache = {}
        for f in feedbacks:
            # find comments
            comments = db.feedback_comments.find(
                {"feedback_id": f.get("_id")}, sort=[("created_at", DESCENDING)]
            )

            comments_list = [
                {
                    "text": c.get("text"),
                    "created_at": c.get("created_at"),
                    "created_by": UserService.get_cached_name(cache, c.get("user_id")),
                }
                for c in comments
            ]

            results.append(
                {
                    "create_at": f.get("created_at"),
                    "text": f.get("text"),
                    "category": f.get("category"),
                    "attachment_files": f.get("attachment_files"),
                    "comments": comments_list,
                }
            )
        return results
