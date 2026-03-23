# services/prompt_template_service.py
from pymongo import DESCENDING

from ..database import db
from ..models.prompt_template import (
    PromptTemplateInDB,
    PromptTemplateBase,
    PromptTemplateData,
)
from bson import ObjectId, Regex


def get_all_prompt_templates(project_id: str):
    if not project_id:
        return []

    data = db.prompt_templates.find({"project": ObjectId(project_id)}).sort(
        "used_at", DESCENDING
    )
    heads = [
        PromptTemplateData(
            title=d["title"] if "title" in d else d["content"][:16] + "...",
            id=str(d["_id"]),
            content=d["content"],
        )
        for d in data
    ]
    return heads


def get_all_shared_prompt_templates(project_id: str, search_text: str = ""):
    if not project_id:
        return []

    data = db.prompt_templates.find(
        {
            "$or": [
                {"title": Regex(search_text, "i")},
                {"content": Regex(search_text, "i")},
            ],
            "project": {"$ne": ObjectId(project_id)},
            "is_shared": True,
        }
    ).limit(20)

    heads = [
        PromptTemplateData(
            title=d["title"] if "title" in d else d["content"][:16] + "...",
            id=str(d["_id"]),
            content=d["content"],
        )
        for d in data
    ]
    return heads


def get_prompt_template_by_id(id: str):
    return db.prompt_templates.find_one({"_id": ObjectId(id)})


def create_prompt_template(context_artifact: PromptTemplateBase):
    prompt_template_dict = context_artifact.model_dump(by_alias=True)
    print("save data: ", prompt_template_dict)
    new_prompt_template = db.prompt_templates.insert_one(prompt_template_dict)
    created = db.prompt_templates.find_one({"_id": new_prompt_template.inserted_id})
    return PromptTemplateInDB(**created)


def update_prompt_template(id: str, prompt_template: PromptTemplateBase):
    db.prompt_templates.update_one(
        {"_id": ObjectId(id)}, {"$set": prompt_template.model_dump(by_alias=True)}
    )
    return db.prompt_templates.find_one({"_id": ObjectId(id)})


def delete_prompt_template(id: str):
    db.prompt_templates.delete_one({"_id": ObjectId(id)})
    return True
