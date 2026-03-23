from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
from abc import ABC
from typing import List, Union

from fastapi import HTTPException
from google import genai

from .LLMBase import LLMBase
from .LLMModelDeclaration import LLMModelDeclaration
from .file_utils import download_file_as_byte
from .types.LLMNames import LLMNames
from .types.models import ModelDeclaration
from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage
from ..services.s3_services import S3UploadServices, FileCategory
from ..services.usage_log_service import UsageLogService


class GeminiLLM_genai_video(LLMBase, ABC):

    def __init__(self):
        api_key = os.environ["GEMINI_API_KEY"]
        self.client = genai.Client(api_key=api_key)

    def download_image(self, url):
        import requests
        import tempfile
        from pathlib import Path

        print("Downloading image from ", url)
        response = requests.get(url)
        if response.status_code != 200:
            return None, None

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(url).suffix
        ) as temp_file:
            temp_file.write(response.content)
            # Get the temporary file path
            temp_file_path = temp_file.name

        print("Uploading file...")
        file_id = self.client.files.upload(file=temp_file_path)
        print("file_id: ", file_id)
        return file_id, temp_file_path

    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model,
        options: dict = None,
        # temperature: Optional[float] = None,
    ):

        prompt = messages[-1]["content"]  # assume last prompt as text
        # search for image in previous message
        image_url, content_type, image = None, None, None
        print("messages: ", messages)
        if len(messages) > 1 and isinstance(messages[-2]["content"], list):
            for p in messages[-2]["content"]:
                if p["type"] == "file_url" and "image" in p.get("file_url").get(
                    "content_type"
                ):
                    image_url = p.get("file_url").get("url")
                    content_type = p.get("file_url").get("content_type")
                    break
        print("image_url", image_url)
        if image_url:
            image_data = download_file_as_byte(image_url)
            image = {"image_bytes": image_data, "mime_type": content_type}

        files, meta = await self.generate_video(model, prompt, image)
        return None, None, files, meta

    async def generate_video(
        self,
        model: str,
        prompt: str,
        image: dict = None,
    ):

        start_t = time.time()
        print(
            "OpenAILLM.GeminiLLM_genai_video: prompt:>>>",
            prompt,
            "has_image" if image else "No image",
        )

        model_spec = LLMModelDeclaration.get_model(model)
        params = dict(model=model, prompt=prompt)
        if image:
            params["image"] = image
        operation = await self.client.aio.models.generate_videos(**params)

        # This loop checks the job status every 10 seconds.
        MAX_WAIT = 60 * 5  # 5 minutes
        while not operation.done and MAX_WAIT > 0:
            await asyncio.sleep(10)
            operation = await self.client.aio.operations.get(operation)
            print("waiting video generation...")
            MAX_WAIT -= 10

        if not operation.done:
            raise HTTPException(
                status_code=500, detail="Timeout during video generation"
            )

        print("OpenAILLM.GeminiLLM_genai_video: response:<<<", operation.model_dump())

        generated_video = operation.response.generated_videos[0]
        video_bytes = self.client.files.download(file=generated_video.video)
        print("Downloaded video size: ", len(video_bytes))
        filename = uuid.uuid4().hex + ".mp4"
        file_url = await S3UploadServices.upload_generate_file(
            filename, video_bytes, FileCategory.GENERATED, "video/mp4", True
        )

        meta = operation.model_dump()
        meta["estimate_price"] = model_spec.unit_price
        meta["company"] = LLMNames.GEMINI.name
        meta["model"] = model
        meta["elapsed_in_sec"] = time.time() - start_t
        UsageLogService.register_usage_meta(meta, LLMNames.GEMINI)
        return [
            dict(file_url=file_url, file_name=filename, content_type="video/mp4")
        ], meta

    # -----
    # https://ai.google.dev/gemini-api/docs/pricing
    models: List[ModelDeclaration] = [
        ModelDeclaration(
            name="veo-3.0-fast-generate-001",
            company=LLMNames.GEMINI,
            unit_price=1.2,  # 0.15 * 8s
            # max_token="128k",
            eligible=True,
            is_video_model=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#veo-3-fast",
            input_modality="TI",
            output_modality="V",
            expensive=True,
        ),
    ]
