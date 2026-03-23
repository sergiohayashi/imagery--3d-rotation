from typing import Optional

from pydantic import BaseModel


class PostFeedbackRequest(BaseModel):
    category: str
    text: str
    attachment_files: Optional[list[str]] = None


class PostFeedbackCommentRequest(BaseModel):
    text: str
