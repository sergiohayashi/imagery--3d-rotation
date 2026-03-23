from datetime import datetime
from typing import Optional, List, Union

from bson import ObjectId
from pydantic import BaseModel
from pydantic import Field

from app.models.chat_message import OutputTypes


class ChatBase(BaseModel):
    user: ObjectId
    project: ObjectId
    initialArtifact: ObjectId = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ChatInDB(ChatBase):
    id: ObjectId = Field(..., alias="_id")
    startTime: datetime
    endTime: datetime = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ChatWithContent(BaseModel):
    id: str
    startTime: Optional[datetime] = None
    endTime: Optional[datetime] = None
    owner: Optional[str] = None
    title: str
    isOwner: Optional[bool] = False
    content: Optional[str] = None


class ChatWithTitle(BaseModel):
    id: str
    startTime: Optional[datetime] = None
    endTime: Optional[datetime] = None
    owner: Optional[str] = None
    is_bookmarked: Optional[bool] = False
    branch_model: Optional[str] = None
    title: str
    isOwner: Optional[bool] = False


class ChatOutputItemFile(BaseModel):
    type: str = OutputTypes.FILE.value
    file_name: Optional[str] = None
    file_url: str
    content_type: str


class ChatUserEntry(BaseModel):
    role: str
    content: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    entry_id: str
    meta: Optional[dict] = None
    augmented_message_log_id: Optional[str] = None
    offset: Optional[int] = None
    agent_action_id: Optional[str] = None
    is_alternative: Optional[int] = 0
    output: Optional[List[Union[ChatOutputItemFile]]]  # adicionar outros...


class ChatSharedListItem(BaseModel):
    shared_id: str
    title: Optional[str] = None
    shared_id_expire_date: Optional[datetime] = None


class SharedChatUserEntry(BaseModel):
    role: str
    content: Optional[str] = None
    image_url: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    augmented_message_log_id: Optional[str] = None
    meta: Optional[dict] = None


class SharedChatWithEntries(BaseModel):
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    shared_id_expire_date: Optional[datetime] = None
    entries: Optional[list[SharedChatUserEntry]] = None


class ChatEntriesForSelection(BaseModel):
    role: str
    content: Optional[str] = None
    image_url: Optional[str] = None
    file_url: Optional[str] = None
    entry_id: str
    files: Optional[str] = None
