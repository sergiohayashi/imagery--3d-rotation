from typing import Optional

from bson import ObjectId
from pydantic import BaseModel
from pydantic import Field


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    email: str = Field(..., min_length=10, max_length=512)
    role: str


class UserInDB(UserBase):
    password: Optional[str] = Field(None, alias="password")
    id: ObjectId = Field(..., alias="_id")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ExternalUserAdd(BaseModel):
    name: str
    email: str
    password: str
    tenant_id: Optional[str] = None


class ExternalUserDelete(BaseModel):
    email: str
