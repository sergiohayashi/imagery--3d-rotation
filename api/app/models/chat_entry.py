from bson import ObjectId
from fastapi import HTTPException
from pydantic import BaseModel, validator
from pydantic import Field
from datetime import datetime

from starlette import status


class ChatEntryBase(BaseModel):
    # chat: str  # change this to str
    chat: ObjectId
    role: str
    message: str = Field(..., min_length=2, max_length=16 * 1024 * 1024)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    @validator("chat")
    @classmethod
    def validate_chat(cls, chat):
        try:
            return ObjectId(chat)
        except Exception:
            raise HTTPException(
                detail="Invalid chat id", status_code=status.HTTP_400_BAD_REQUEST
            )


class ChatEntryInDB(ChatEntryBase):
    id: ObjectId = Field(..., alias="_id")
    datetime: datetime
    meta: str

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
