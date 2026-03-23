from pydantic import BaseModel
from typing import Optional, List


class OpBoostChatMessage(BaseModel):
    role: str
    content: str


class Message(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class Choice(BaseModel):
    index: Optional[int] = None
    message: Optional[Message] = None
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class OpBoostChatCompletion(BaseModel):
    id: Optional[str] = None
    object: Optional[str] = None
    created: Optional[int] = None
    model: Optional[str] = None
    choices: Optional[List[Choice]] = None
    usage: Optional[Usage] = None
    elapsed_in_sec: Optional[float] = None
    estimate_price: Optional[float] = None
    company: Optional[str] = None
    image_generation_response: Optional[dict] = None
