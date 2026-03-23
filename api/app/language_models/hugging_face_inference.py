import os
import time
from abc import ABC
from typing import List, Union, Any

from huggingface_hub import AsyncInferenceClient

from app.language_models.LLMBase import LLMBase
from app.language_models.hugging_face_models import HuggingFaceModels
from app.language_models.openai_commons import get_async_client
from app.language_models.types.LLMNames import LLMNames
from app.language_models.types.models import ModelDeclaration
from app.language_models.types.opboos_chat_completion import OpBoostChatMessage
from app.services.pricing import (
    calculate_estimate_price,
    calculate_estimate_price_for_hf,
)
from app.services.usage_log_service import UsageLogService


class HuggingFaceModelListLoader:
    pass


class HuggingFaceInferenceApi(LLMBase):

    @staticmethod
    def _get_async_client():
        async_client = AsyncInferenceClient(
            provider="auto", api_key=os.getenv("HF_API_TOKEN")
        )
        return async_client

    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model: str,
        options: dict = None,
    ):
        start_t = time.time()
        model_spec = HuggingFaceModels.get_model(model)

        # build message
        messages_to_send = []
        for m in messages:
            if isinstance(m["content"], str):
                if m.get("content"):
                    messages_to_send.append(
                        {"role": m.get("role"), "content": m.get("content")}
                    )
            else:
                _contents = []
                for p in m["content"]:
                    if p["type"] == "text":
                        if not p.get("text") or p.get("text") == "(empty)":
                            continue
                        _contents.append({"type": "text", "text": p.get("text")})
                    elif p["type"] == "image_url":
                        _file = p.get("image_url")
                        _contents.append(p)  # format is already correct
                    elif p["type"] == "file_url":
                        _file = p.get("file_url")
                        if "image" in _file.get("content_type"):
                            _contents.extend(
                                [
                                    {
                                        "type": "text",
                                        "text": f'filename: {_file.get("file_name")}',
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": _file.get("url")},
                                    },
                                ]
                            )
                        else:
                            continue

                messages_to_send.append({"role": m.get("role"), "content": _contents})

        # call the model
        # print(f'HuggingFaceInferenceApi.achat>> messages: {messages_to_send}')
        # print(f'HuggingFaceInferenceApi.achat>> Model: {model_spec.id}')
        response = (
            await HuggingFaceInferenceApi._get_async_client().chat.completions.create(
                model=model_spec.id,
                messages=messages_to_send,
            )
        )

        # collect response and meta data
        print("HuggingFaceInferenceApi.achat: response:<<<", response)
        answer = response.choices[0].message.content
        meta = dict(response)
        meta["estimate_price"], meta["input_tokens"], meta["output_tokens"] = (
            calculate_estimate_price_for_hf(model_spec, meta["usage"])
        )
        meta["elapsed_in_sec"] = time.time() - start_t
        meta["company"] = model_spec.company
        meta["model"] = model_spec.name
        UsageLogService.register_usage_meta(meta, LLMNames.OPENAI)
        return answer, None, None, meta

    # models..
    models: List[ModelDeclaration] = []
