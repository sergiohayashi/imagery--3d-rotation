from typing import Optional
from datetime import datetime

# from bson import ObjectId
from pydantic import BaseModel, Field, validator


class SystemMessageBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=16 * 1024 * 1024)
    project: str = Field(..., description="The project id")
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    is_shared: Optional[bool] = False
    used_at: Optional[datetime] = None


class SystemMessageForUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=16 * 1024 * 1024)
    title: Optional[str] = Field(None, min_length=1, max_length=100)


class SystemMessageList(BaseModel):
    id: str
    title: Optional[str] = None


class SystemMessageData(BaseModel):
    id: str
    content: str
    title: Optional[str] = None
