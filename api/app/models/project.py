from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from pydantic import Field


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    description: Optional[str] = None


class ProjectInDB(ProjectBase):
    admin: ObjectId = Field(..., alias="_id")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ProjectWithRole(BaseModel):
    name: str
    description: Optional[str] = None
    id: str
    role: str
