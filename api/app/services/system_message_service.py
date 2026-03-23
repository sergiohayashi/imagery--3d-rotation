# services/system_message_service.py
from datetime import datetime

from fastapi import HTTPException
from pymongo import DESCENDING
from starlette import status

from ..database import db
from ..models.system_message import (
    SystemMessageBase,
    SystemMessageData,
    SystemMessageForUpdate,
)
from bson import ObjectId, Regex


def get_all_system_messages(project_id: str):
    if not project_id:
        return []

    data = db.system_messages.find({"project": ObjectId(project_id)}).sort(
        "used_at", DESCENDING
    )
    heads = [
        SystemMessageData(
            title=d["title"] if "title" in d else d["content"][:16] + "...",
            id=str(d["_id"]),
            content=d["content"],
        )
        for d in data
    ]
    return heads


def get_all_shared_system_messages(project_id: str, search_text: str = ""):
    if not project_id:
        return []

    # data = db.system_messages.find(
    #     {"project": {"$ne": ObjectId(project_id)}, "is_shared": True})

    data = (
        db.system_messages.find(
            {
                "$or": [
                    {"title": Regex(search_text, "i")},
                    {"content": Regex(search_text, "i")},
                ],
                # "project": {"$ne": ObjectId(project_id)},
                "is_shared": True,
            }
        )
        .sort("used_at", DESCENDING)
        .limit(20)
    )

    heads = [
        SystemMessageData(
            title=d["title"] if "title" in d else d["content"][:16] + "...",
            id=str(d["_id"]),
            content=d["content"],
        )
        for d in data
    ]
    return heads


def get_system_message_by_id(id: str):
    obj = db.system_messages.find_one({"_id": ObjectId(id)})
    return (
        {
            "id": str(obj["_id"]),
            "content": obj["content"],
            "title": obj["title"] if "title" in obj else "(title)",
        }
        if obj
        else None
    )


def create_system_message(args: SystemMessageBase):
    system_message_dict = {
        "content": args.content,
        "is_shared": args.is_shared,
        "project": ObjectId(args.project),
        "title": args.title,
        # "type": args.type,
        "used_at": datetime.now(),
    }
    inserted = db.system_messages.insert_one(system_message_dict)
    return {"id": str(inserted.inserted_id)}


def update_system_message(id: str, new_data: SystemMessageForUpdate):
    cur = db.system_messages.find_one({"_id": ObjectId(id)})
    if not cur:
        raise HTTPException(
            detail="Invalid id", status_code=status.HTTP_400_BAD_REQUEST
        )

    new_data = new_data.model_dump()
    new_data["title"] = new_data["title"] or cur["title"]
    new_data["used_at"] = datetime.now()
    db.system_messages.update_one({"_id": ObjectId(id)}, {"$set": new_data})


def delete_system_message(id: str):
    db.system_messages.delete_one({"_id": ObjectId(id)})
    return True


def touch(_id: str):
    db.system_messages.update_one(
        {"_id": ObjectId(_id)}, {"$set": {"used_at": datetime.now()}}
    )
