from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, Field


class OutputTypes(str, Enum):
    FILE = "file"
    # adicionar outros...


class RetryOptions(BaseModel):
    model: str
    entry_id: str


# class ToolsOptions(BaseModel):
#     use_search: Optional[bool] = False
#     use_code: Optional[bool] = False
#     use_image_generation: Optional[bool] = False
#     # use_url_context: Optional[bool] = False


class ModelWithParameters(BaseModel):
    name: str
    reasoning_effort: Optional[str] = None
    use_search: Optional[bool] = False
    use_code: Optional[bool] = False
    use_image_generation: Optional[bool] = False
    response_mime_type: Optional[str] = None
    response_json_schema: Optional[dict[str, Any]] = None


class ChatMessage(BaseModel):
    message: Optional[str] = Field("", max_length=16 * 1024 * 1024)
    use_model: Optional[str | list[str | ModelWithParameters]] = None
    preset_list: Optional[List[dict]] = None
    use_sliding_window: Optional[bool] = False
    context_artifacts: Optional[List[str]] = None
    system_message: Optional[str] = None
    system_message_onetime_content: Optional[str] = None
    prompts: Optional[List[str]] = None
    chat_id: Optional[str] = None
    image_url: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    data_store: Optional[str] = None
    project_id: str
    file_context_id: Optional[str] = None
    offset: Optional[int] = None
    temporary_chat: Optional[bool] = False

    # when this parameter is set, the system will generate a new answer using the specified model (alternative)
    retry_entry_id: Optional[str] = None
    title: Optional[str] = "undefined"
    imagery_args: Optional[dict] = {}


# class ChatMessageWithFork(BaseModel):
#     message: Optional[str] = Field('', max_length=16 * 1024 * 1024)
#     use_model: Optional[str] = None
#     chat_id: Optional[str] = None
#     temperature: Optional[float] = None
#     project_id: str
#     fork_entry_id: Optional[str] = None
#     title: Optional[str] = None
#     options: Optional[ToolsOptions] = None
#     # user_id: str


class ChatMessageWithForkWithEntries(BaseModel):
    message: Optional[str] = Field("", max_length=16 * 1024 * 1024)
    use_model: Optional[str | list[str | ModelWithParameters]] = None
    chat_id: Optional[str] = None
    entries: List[str]
    temperature: Optional[float] = None
    project_id: str
    fork_entry_id: Optional[str] = None
    title: Optional[str] = None
    # options: Optional[ToolsOptions] = None
    # user_id: str


class BranchInNewChatParams(BaseModel):
    chat_id: str
    entry_id: str
    project_id: str


class ChatSimpleMessage(BaseModel):
    system_message: str
    message: Optional[str] = ""
    use_model: Optional[str] = None
    image_url: Optional[str] = None
    temperature: Optional[float] = None


class ChatMessageNext(BaseModel):
    use_sliding_window: Optional[bool] = False
    chat_id: Optional[str] = None
    project_id: str
    entry_id: str


class ChatResponse(BaseModel):
    response: Optional[str | list[str]] = None
    meta: Optional[str] = None
    chat_id: str
    errors: Optional[str | List[Any]] = None
    # window_first_entry_id: Optional[str] = None


class ChatSimpleResponse(BaseModel):
    response: str
    meta: Optional[str] = None
