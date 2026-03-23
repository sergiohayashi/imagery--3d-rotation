from __future__ import annotations

from datetime import datetime
from app.database_async import db_async
from bson import ObjectId


class UsageLogServiceAsync:

    @classmethod
    async def get_current_usage(cls, user_id):
        now = datetime.now()
        result = await db_async.users_usage.find_one(
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
