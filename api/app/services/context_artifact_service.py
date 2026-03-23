# services/context_artifact_service.py
from datetime import datetime

from fastapi import HTTPException
from pymongo import DESCENDING
from starlette import status

from ..database import db
from ..models.context_artifact import (
    ContextArtifactBase,
    ContextArtifactData,
    ContextArtifactForUpdate,
)
from bson import ObjectId


def get_all_context_artifacts(project_id: str, titles_only: bool):
    if not project_id:
        return []
    data = db.context_artifacts.find({"project": ObjectId(project_id)}).sort(
        "used_at", DESCENDING
    )
    heads = [
        ContextArtifactData(
            title=d["title"] if "title" in d else d["content"][:16] + "...",
            id=str(d["_id"]),
            content=d["content"] if not titles_only else None,
        )
        for d in data
    ]
    return heads


def get_context_artifact_by_id(id: str):
    d = db.context_artifacts.find_one({"_id": ObjectId(id)})
    return ContextArtifactData(
        id=str(d["_id"]),
        content=d["content"],
        title=d["title"] if "title" in d else d["content"][:16] + "...",
    )


def create_context_artifact(args: ContextArtifactBase):
    context_artifact_dict = {
        "content": args.content,
        "project": ObjectId(args.project),
        "title": args.title,
    }
    new_context_artifact = db.context_artifacts.insert_one(context_artifact_dict)
    return {"id": str(new_context_artifact.inserted_id)}


def update_context_artifact(id: str, context_artifact: ContextArtifactForUpdate):
    cur = db.context_artifacts.find_one({"_id": ObjectId(id)})
    if not cur:
        raise HTTPException(
            detail="Invalid id", status_code=status.HTTP_400_BAD_REQUEST
        )
    data = context_artifact.model_dump()
    data["title"] = data["title"] or cur["title"]
    data["used_at"] = datetime.now()
    db.context_artifacts.update_one({"_id": ObjectId(id)}, {"$set": data})


def delete_context_artifact(id: str):
    db.context_artifacts.delete_one({"_id": ObjectId(id)})
    return True


def touch(_id: str):
    db.context_artifacts.update_one(
        {"_id": ObjectId(_id)}, {"$set": {"used_at": datetime.now()}}
    )
