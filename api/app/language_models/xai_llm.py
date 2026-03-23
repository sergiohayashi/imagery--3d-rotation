from __future__ import annotations

import json
import os
import time
import traceback
from abc import ABC
from typing import List, Union

import openai
from openai import NOT_GIVEN
from openai.types.chat import ChatCompletion

from .LLMBase import LLMBase
from .LLMModelDeclaration import LLMModelDeclaration
from .file_utils import download_file_as_byte
from .types.LLMNames import LLMNames
from .types.models import ModelDeclaration
from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage
from ..services.pricing import calculate_estimate_price
from ..services.usage_log_service import UsageLogService


def parse_json_response(response: ChatCompletion):
    json_response = response.choices[0].message.content
    json_response = json_response.replace("```json", "").replace("```", "").strip()
    try:
        parse_json = json.loads(json_response, strict=False)
    except Exception as e:
        print(f"Error parsing json string: type(e)={type(e)}. Error occurred: {e}")
        traceback.print_exc()
        parse_json = response.choices[0].message.content

    return parse_json


markdown_instruction = "Formatting re-enabled"
# markdown_instruction = "Please format your response using proper markup and code formatting where applicable. For example, use Markdown for headings, lists, and inline code, and format code blocks with appropriate syntax highlighting. Ensure that all code snippets are enclosed in triple backticks (```) with the correct language specified for clarity"

xai_api_key = os.getenv("XAI_API_KEY")
xai_base_url = "https://api.x.ai/v1"


class xAILLM(LLMBase, ABC):

    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model: str,
        options: dict = None,
    ) -> (dict | str, OpBoostChatCompletion):

        start_t = time.time()

        print("xAILLM.achat: message[-1]:>>>", messages[-1])
        model_spec = LLMModelDeclaration.get_model(model)
        # if model_spec.force_temperature:
        #     temperature = model_spec.force_temperature

        print(
            f"{model} reasoning_effort: {model_spec.reasoning_effort if model_spec.reasoning_effort else NOT_GIVEN}"
        )

        if model_spec.force_system_message_to_inject:
            print(
                "Force inject system message: ",
                model_spec.force_system_message_to_inject,
            )
            messages = [
                {
                    "role": "system",
                    "content": model_spec.force_system_message_to_inject,
                }
            ] + messages

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
                            # convert to image format
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
                            try:
                                print("Downloading from file", _file)
                                content_as_bytes = download_file_as_byte(
                                    _file.get("url")
                                )
                                file_as_text = content_as_bytes.decode("utf-8")
                                _contents.extend(
                                    [
                                        {
                                            "type": "text",
                                            "text": f"filename: {_file.get('file_name')}",
                                        },
                                        {"type": "text", "text": file_as_text},
                                    ]
                                )
                                print(f"send {_file.get('file_name')} as text")
                            except UnicodeDecodeError:
                                _contents.extend(
                                    [
                                        {
                                            "type": "text",
                                            "text": f"filename: {_file.get('file_name')}",
                                        },
                                        {
                                            "type": "text",
                                            "text": "(content can not be provided)",
                                        },
                                    ]
                                )
                        # else:
                        #     print( f'"xai dont accept file. Ignore..{_file.get("url")}')
                        #     continue

                messages_to_send.append({"role": m.get("role"), "content": _contents})

        print(f"messages_to_send: {messages_to_send}")

        response = await openai.AsyncOpenAI(
            api_key=xai_api_key, base_url=xai_base_url
        ).chat.completions.create(
            model=model,
            messages=messages_to_send,
            # temperature=config.default_temperature if temperature is None else temperature,
            reasoning_effort=(
                model_spec.reasoning_effort
                if model_spec.reasoning_effort
                else NOT_GIVEN
            ),
        )
        print("xAILLM.achat: response:<<<", response)
        # UsageLogService.register_usage(response)
        answer = response.choices[0].message.content
        meta = response.model_dump()
        meta["elapsed_in_sec"] = time.time() - start_t
        meta["estimate_price"], meta["input_tokens"], meta["output_tokens"] = (
            calculate_estimate_price(model, meta["usage"])
        )
        meta["company"] = LLMNames.XAI.name
        UsageLogService.register_usage_meta(meta, LLMNames.XAI)
        return answer, None, None, meta



    async def generate_image(self, prompt: str, model: str) -> (str, dict):

        raise Exception("Not implemented")

    models: List[ModelDeclaration] = [
        ModelDeclaration(
            name="grok-4-1-fast-reasoning",
            company=LLMNames.XAI,
            # description="",
            input_price=0.2,
            output_price=0.5,
            eligible=True,
            max_token="2M",
            link="https://docs.x.ai/docs/models/grok-4-1-fast-reasoning",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="grok-4-1-fast-non-reasoning",
            company=LLMNames.XAI,
            # description="",
            input_price=0.2,
            output_price=0.5,
            eligible=True,
            max_token="2M",
            link="https://docs.x.ai/docs/models/grok-4-1-fast-non-reasoning",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="grok-4-fast-reasoning",
            company=LLMNames.XAI,
            # description="",
            input_price=0.2,
            output_price=0.5,
            eligible=True,
            max_token="2M",
            link="https://docs.x.ai/docs/models/grok-4-fast-reasoning",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="grok-4-fast-non-reasoning",
            company=LLMNames.XAI,
            # description="",
            input_price=0.2,
            output_price=0.5,
            eligible=True,
            max_token="2M",
            link="https://docs.x.ai/docs/models/grok-4-fast-non-reasoning",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="grok-4-0709",
            company=LLMNames.XAI,
            # description="",
            input_price=3,
            output_price=15,
            eligible=True,
            max_token="256k",
            link="https://docs.x.ai/docs/models",
            input_modality="T",
            output_modality="T",
        ),
        ModelDeclaration(
            name="grok-code-fast-1",
            company=LLMNames.XAI,
            # description="",
            input_price=0.2,
            output_price=1.5,
            eligible=True,
            max_token="256k",
            link="https://docs.x.ai/docs/models",
            input_modality="T",
            output_modality="T",
        ),

        ModelDeclaration(
            name="grok-3-mini",
            company=LLMNames.XAI,
            # description="",
            input_price=0.3,
            output_price=0.5,
            eligible=True,
            max_token="131k",
            link="https://docs.x.ai/docs/models",
            input_modality="T",
            output_modality="T",
        ),

    ]
