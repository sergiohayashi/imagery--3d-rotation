from pydantic import BaseModel
from typing import Optional, List

from .LLMNames import LLMNames


class ModelDeclaration(BaseModel):
    name: str
    company: LLMNames
    description: Optional[str] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    image_input_price: Optional[float] = None
    unit_price: Optional[float] = None
    code_interpreter_price_per_container: Optional[float] = None
    eligible: bool
    is_image_model: Optional[bool] = False
    is_video_model: Optional[bool] = False
    restricted_to_users: Optional[str] = None
    # is_vision_enabled: Optional[bool]= False
    max_token: Optional[str] = None
    knowledge_cutoff: Optional[str] = None
    # force_temperature: Optional[float]=None
    reasoning_effort: Optional[str] = None
    expensive: Optional[bool] = False
    force_system_message_to_inject: Optional[str] = None
    # accept_temperature: Optional[bool] = True
    # can_generate_image: Optional[bool]= False
    quality: Optional[str] = None
    max_output_tokens: Optional[int] = None
    link: Optional[str] = None
    has_web_search: Optional[bool] = False
    has_image_generation: Optional[bool] = False
    force_image_generation_option: Optional[bool] = False
    has_code_interpreter: Optional[bool] = False
    has_url_context: Optional[bool] = False
    input_modality: str = ""
    output_modality: str = ""
    effort_options: List[str] = []
    accept_system_message: bool = True
