from bson import ObjectId
from pymongo import DESCENDING

from app.database import db


def get_last_prompts(project_id, titles_only):
    if not project_id:
        return []

    # get the latest chat entries
    data = (
        db.chat_entries.find({"project_id": ObjectId(project_id), "role": "user"})
        .sort("created_at", DESCENDING)
        .limit(30)
    )
    data = [
        {
            "id": str(d.get("_id")),
            "content": d.get("content"),
            "file_url": d.get("file_url"),
            "image_url": d.get("iamge_url"),
        }
        for d in data
    ]
    return data


def get_last_prompt_by_id(id):
    return None
