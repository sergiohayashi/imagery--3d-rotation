from typing import Optional
from datetime import datetime

# from bson import ObjectId
from pydantic import BaseModel, Field, validator


class FileContext(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    project_id: str


class RagContextFile(BaseModel):
    file_name: str
    file_url: str
