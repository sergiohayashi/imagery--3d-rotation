# routes/upload_routes.py

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse
import logging

from ..config.config import config
from ..language_models.LLMModelDeclaration import LLMModelDeclaration
from ..language_models.hugging_face_models import HuggingFaceModels
from ..services.user_service import UserService

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/models")
def get_models_list():
    _, email = UserService.get_current_user()

    models = []
    for key, value in LLMModelDeclaration.get_all_models_as_dict().items():
        if not value.eligible:
            continue
        if value.restricted_to_users:
            if email not in value.restricted_to_users.split(","):
                continue
        models.append(
            {
                "company": value.company.name,
                "name": key,
                "description": value.description,
                "input_price": value.input_price,
                "output_price": value.output_price,
                "unit_price": value.unit_price,
                "max_token": value.max_token,
                "knowledge_cutoff": value.knowledge_cutoff,
                "is_default": key == config.default_model,
                # "is_vision_enabled": value.is_vision_enabled,
                "reasoning_effort": value.reasoning_effort,
                "expensive": value.expensive,
                "is_image_model": value.is_image_model,
                "has_search": value.has_web_search,
                "has_code": value.has_code_interpreter,
                "has_image_generation": value.has_image_generation,
                # "has_url_context": value.has_url_context,
                "link": value.link,
                "input_modality": value.input_modality,
                "output_modality": value.output_modality,
                "effort_options": value.effort_options,
            }
        )

    return JSONResponse(status_code=200, content=models)


@router.get("/open-models")
def get_open_models():
    _, email = UserService.get_current_user()
    models = [m.model_dump() for m in HuggingFaceModels.get_models()]
    return models
