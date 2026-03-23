from datetime import datetime
from typing import Optional

# from bson import ObjectId
from pydantic import BaseModel, Field, validator


class ContextArtifactBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=16 * 1024 * 1024)
    title: Optional[str] = Field(..., min_length=1, max_length=100)
    project: str = Field(..., description="The project id")
    used_at: Optional[datetime] = None

class ContextArtifactForUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=16 * 1024 * 1024)
    title: Optional[str] = Field(None, min_length=1, max_length=100)


class ContextArtifactData(BaseModel):
    id: str
    content: Optional[str] = None
    title: Optional[str] = None
