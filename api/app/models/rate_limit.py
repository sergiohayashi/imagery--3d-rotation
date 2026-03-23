from bson import ObjectId
from pydantic import BaseModel
from pydantic import Field


class RateLimitBase(BaseModel):
    user: ObjectId
    ratePerMinute: int
    ratePerDay: int

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class RateLimitInDB(RateLimitBase):
    id: ObjectId = Field(..., alias="_id")

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
