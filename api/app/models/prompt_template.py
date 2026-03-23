from datetime import datetime
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field, validator


class PromptTemplateBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=16 * 1024 * 1024)
    project: ObjectId = Field(..., description="The project id")
    title: Optional[str] = None
    is_shared: Optional[bool] = False
    used_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    @validator("project", pre=True)
    @classmethod
    def convert_project_to_object_id(cls, v):
        return ObjectId(v)


class PromptTemplateInDB(PromptTemplateBase):
    id: ObjectId = Field(..., alias="_id")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class PromptTemplateList(BaseModel):
    id: str
    title: Optional[str] = None


class PromptTemplateData(BaseModel):
    id: str
    content: str
    title: Optional[str] = None
