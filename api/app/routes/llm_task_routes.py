from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.llm_task_services import LLMTaskServices

router = APIRouter()


class PromptParameter(BaseModel):
    prompt: str


class TextParameter(BaseModel):
    text: str
    type: Optional[str] = "text"


@router.post("/llm_task/translate")
async def translate(arg: PromptParameter):
    return await LLMTaskServices.translate(arg.prompt)


@router.post("/llm_task/improve_prompt")
async def improve_prompt(arg: PromptParameter):
    return await LLMTaskServices.improve_prompt(arg.prompt)


@router.post("/llm_task/improve-my-text")
async def improve_text(arg: TextParameter):
    if arg.type == "prompt":
        return await LLMTaskServices.improve_prompt(arg.text)
    else:
        return await LLMTaskServices.improve_text(arg.text)
