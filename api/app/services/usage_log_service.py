from __future__ import annotations

from datetime import datetime
from typing import Union

from ..language_models.types.LLMNames import LLMNames
from ..language_models.types.opboos_chat_completion import OpBoostChatCompletion
from ..config.config import config

from ..database import db

from bson import ObjectId


class UsageLogServices:
    openai = "openai"


class UsageLogService:
    @staticmethod
    def register_usage_meta(
        meta: Union[OpBoostChatCompletion, dict], service: LLMNames = LLMNames.OPENAI
    ):
        user_id = config.user_info_var.get()["user_id"]
        estimate_price = (
            meta["estimate_price"] if isinstance(meta, dict) else meta.estimate_price
        )
        meta = meta if isinstance(meta, dict) else meta.model_dump()

        # delete content from log
        # clean_meta = {**meta, "choices": "(deleted)", "candidates": "(deleted)", "output": "(deleted)", 'content': "(deleted)"}
        db.usage_log.insert_one(
            {
                "user_id": ObjectId(user_id),
                "tenant_id": config.user_info_var.get()["tenant_id"],
                "datetime": datetime.now(),
                "meta": meta,
                "service": service.name,
                "estimate_price": estimate_price,
            }
        )

        # update the monthly usage
        now = datetime.now()
        db.users_usage.update_one(
            # filter query
            {
                "user_id": ObjectId(user_id),
                "tenant_id": config.user_info_var.get()["tenant_id"],
                "year": now.year,
                "month": now.month,
            },
            # update query
            {"$inc": {"estimate_total_cost": estimate_price or 0, "count": 1}},
            upsert=True,  # create new document, if not exist
        )

    @classmethod
    def get_current_usage(cls, user_id):
        now = datetime.now()
        result = db.users_usage.find_one(
            {"user_id": ObjectId(user_id), "year": now.year, "month": now.month}
        )
        return (
            {
                "balance": round(result.get("estimate_total_cost", 0.0), 2),
                "count": result.get("count", 0),
            }
            if result
            else {"amount": 0.0, "count": 0}
        )

    @classmethod
    def get_ranking_no_tenant(cls, top, month, year):
        # Get the current year and month
        if not year:
            current_year = datetime.now().year
            current_month = datetime.now().month
        else:
            current_year = year
            current_month = month + 1

        # Find the top 3 users with the highest 'count' for the current year and month
        top_users = db.users_usage.find(
            {
                "year": current_year,
                "month": current_month,
                # 'count': {'$gte': 4}
            }
        ).sort("count", -1)

        # Iterate through the top users and fetch their first names from the 'user' collection
        top_users_with_names = []
        for user_usage in top_users:
            user_id = user_usage["user_id"]
            user = db.users.find_one({"_id": user_id})
            if (
                user
                and "Teste" not in user["name"]
                and not user.get("exclude_from_ranking", False)
            ):
                first_name = user["name"].split()[0]
                top_users_with_names.append(
                    {
                        "user_id": str(user_id),
                        "count": user_usage["count"],
                        "first_name": first_name
                        + " "
                        + user["name"].split()[-1][0:1].upper(),
                        # 'first_name': first_name,
                        "name": user["name"],
                    }
                )

        return {
            "ranking": top_users_with_names[:top],
            "month": current_month - 1,
            "year": current_year,
        }
