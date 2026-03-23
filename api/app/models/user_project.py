from typing import Optional

from bson import ObjectId
from pydantic import BaseModel
from pydantic import Field


class UserProjectBase(BaseModel):
    user_id: ObjectId
    project_id: ObjectId
    role: Optional[str] = "contributor"  # contributor or admin

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class UserProjectInDB(UserProjectBase):
    id: ObjectId = Field(..., alias="_id")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
