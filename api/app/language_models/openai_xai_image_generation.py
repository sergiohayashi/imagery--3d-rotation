from __future__ import annotations

import base64
import os
import time
import uuid
from typing import List, Union

import openai
import requests

from .LLMBase import LLMBase
from .LLMModelDeclaration import LLMModelDeclaration
from .types.LLMNames import LLMNames
from .types.models import ModelDeclaration
from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage
from ..services.pricing import calculate_estimate_price
from ..services.s3_services import S3UploadServices, FileCategory
from ..services.usage_log_service import UsageLogService

xai_api_key = os.getenv("XAI_API_KEY")
xai_base_url = "https://api.x.ai/v1"


class xAILLM_ImageGenerate(LLMBase):

    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model: str,
        options: dict = None,
    ) -> (dict | str, OpBoostChatCompletion):

        prompt = messages[-1]["content"]
        image_url, meta = await self.generate_image(prompt, model)
        return None, image_url, None, meta

    async def generate_image(self, prompt: str, model: str) -> (str, dict):
        model_spec = LLMModelDeclaration.get_model(model)

        start_t = time.time()
        print("OpenAILLM.generate_image: prompt:>>>", prompt)
        response = await openai.AsyncOpenAI(
            api_key=xai_api_key, base_url=xai_base_url
        ).images.generate(
            model=model,
            prompt=prompt,
            quality=model_spec.quality or None,
            n=1,
            # size="1024x1024"
        )
        response = response.model_dump()
        print("OpenAILLM.generate_image: response.usage:<<<", response.get("usage"))
        # if not response.data or not response.data[0].url:
        #     raise HTTPException(status_code=500, detail="Failed to generate image.")

        # Download the image from the URL
        if response.get("data")[0].get("url"):
            image_url = response.get("data")[0].get("url")
            image_response = requests.get(image_url)
            image_response.raise_for_status()
            image_bytes = image_response.content
        else:  #
            image_bytes = base64.b64decode(response.get("data")[0].get("b64_json"))

        # Generate a unique file name
        file_name = (
            f"{uuid.uuid4()}.png"  # Assuming the image is a PNG. Adjust if necessary.
        )

        # Upload to S3
        file_url = await S3UploadServices.upload_generate_image(
            file_name, image_bytes, "png", FileCategory.GENERATED
        )

        # response = response.model_dump()
        meta = response
        #
        # meta = OpBoostChatCompletion()
        # meta.image_generation_response = response
        meta["elapsed_in_sec"] = time.time() - start_t
        if response.get("usage"):
            # meta['estimate_price'] = calculate_estimate_price(model, response['usage'])
            meta["estimate_price"], meta["input_tokens"], meta["output_tokens"] = (
                calculate_estimate_price(model, meta["usage"])
            )
        else:
            meta["estimate_price"] = model_spec.unit_price
            meta["input_tokens"], meta["output_tokens"] = 0, 0
        meta["company"] = LLMNames.XAI.name
        if not "model" in meta:
            meta["model"] = model
        UsageLogService.register_usage_meta(meta, LLMNames.OPENAI)
        return file_url, meta

    models: List[ModelDeclaration] = [
        ModelDeclaration(
            name="grok-2-image-1212",
            company=LLMNames.XAI,
            # description="",
            input_price=0,
            image_input_price=0,
            # output_price=10,
            unit_price=0.07,
            eligible=True,
            is_image_model=True,
            max_token=None,
            link="https://docs.x.ai/docs/models",
            input_modality="T",
            output_modality="I",
        ),
    ]
