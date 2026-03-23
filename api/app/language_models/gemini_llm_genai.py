from __future__ import annotations

import base64
import json
import os
import tempfile
import time
import traceback
import uuid
from abc import ABC
from io import BytesIO
from pathlib import Path
from typing import List, Union

from PIL import Image
from google import genai
from google.genai import types

from .LLMBase import LLMBase
from .LLMModelDeclaration import LLMModelDeclaration
from .file_utils import download_file_as_byte
from .types.LLMNames import LLMNames
from .types.models import ModelDeclaration
from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage
from ..models.enums import ChatRole
from ..services.pricing import calculate_estimate_price
from ..services.s3_services import S3UploadServices, FileCategory
from ..services.usage_log_service import UsageLogService


# Custom JSONEncoder that handles bytes.
class BytesEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            # Option 1: Decode if bytes represent UTF-8 text:
            # return obj.decode("utf-8")
            # Option 2: Base64 encode the bytes (suitable for arbitrary binary data):
            return base64.b64encode(obj).decode("utf-8")
        return super().default(obj)


def answer_with_citations_if_exists(response):
    # ref: https://ai.google.dev/gemini-api/docs/google-search
    # Usage: Assuming response with grounding metadata
    # text_with_citations = add_citations(response)
    # print(text_with_citations)

    text = response.text
    try:
        supports = response.candidates[0].grounding_metadata.grounding_supports
        chunks = response.candidates[0].grounding_metadata.grounding_chunks

        # Sort supports by end_index in descending order to avoid shifting issues when inserting.
        sorted_supports = sorted(
            supports, key=lambda s: s.segment.end_index, reverse=True
        )

        for support in sorted_supports:
            end_index = support.segment.end_index
            if support.grounding_chunk_indices:
                # Create citation string like [1](link1)[2](link2)
                citation_links = []
                for i in support.grounding_chunk_indices:
                    if i < len(chunks):
                        uri = chunks[i].web.uri
                        citation_links.append(f"[{i + 1}]({uri})")

                citation_string = ", ".join(citation_links)
                text = text[:end_index] + citation_string + text[end_index:]

        rendered_content = response.candidates[
            0
        ].grounding_metadata.search_entry_point.rendered_content
        return text, rendered_content
    except:
        # ignore, just use text
        pass

    return text, None


def get_grounding_list(response):
    try:
        result = []
        ground_chunks = response.candidates[0].grounding_metadata.grounding_chunks
        for chunks in ground_chunks:
            if chunks.web:
                result.append(
                    {
                        "title": chunks.web.title,
                        "uri": chunks.web.uri,
                    }
                )
        return result
    except:
        pass
    return None


api_key = os.environ.get("GEMINI_API_KEY", None)


class GeminiLLM_genai(LLMBase, ABC):

    def __init__(self):

        self.client = genai.Client(api_key=api_key)
        # genai.configure(api_key=api_key)  # for multitenant, need to check if it is thread safe!

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
        # file_id = genai.upload_file(path=temp_file_path)
        print("file_id: ", file_id)
        return file_id, temp_file_path

    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model,
        options: dict = None,
        # temperature: Optional[float] = None,
    ):
        try:
            self.client = genai.Client(api_key=api_key)
            return await self._achat(messages, model, options)
        finally:
            # parece que nao tem o close
            try:
                if hasattr(self.client, "close"):
                    self.client.close()
                elif hasattr(self.client, "aclose"):
                    await self.client.aclose()
            except Exception as e:
                print(f"Error closing client: {e}. IGNORE")

    async def _achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model,
        options: dict = None,
        # temperature: Optional[float] = None,
    ):
        start_t = time.time()
        # print('GeminiLLM.achat: message[-1]:>>>', messages[-1])
        # print('temperature', config.default_temperature if temperature is None else temperature)

        model_spec = LLMModelDeclaration.get_model(model)

        # convert the message
        gemini_messages = []
        system_message = None
        if messages[0]["role"] == ChatRole.system and model_spec.accept_system_message:
            system_message = messages[0]["content"]
            messages = messages[1:]

        temp_files = []

        # collect the images
        for m in messages:
            if isinstance(m["content"], str):
                gemini_messages.append(
                    dict(
                        role="model" if m["role"] == ChatRole.assistant else "user",
                        parts=[{"text": m["content"]}],
                    )
                )
            else:  # it contain a image
                parts = []
                for p in m["content"]:
                    if p["type"] == "text":
                        parts.append({"text": p.get("text")})
                    if p["type"] == "image_url":
                        image_url = p.get("image_url").get("url")
                        image_data = download_file_as_byte(image_url)
                        image = Image.open(BytesIO(image_data))
                        mime_type = Image.MIME[image.format]
                        parts.append(
                            {
                                "inline_data": {
                                    "data": image_data,
                                    "mime_type": mime_type,
                                }
                            }
                        )
                    if p["type"] == "file_url":
                        file_url = p.get("file_url").get("url")
                        content_as_bytes = download_file_as_byte(file_url)
                        if "pdf" in p.get("file_url").get("content_type"):
                            parts.extend(
                                [
                                    {
                                        "text": f"filename: {p.get('file_url').get('file_name')}"
                                    },
                                    {
                                        "inline_data": {
                                            "data": content_as_bytes,
                                            "mime_type": p.get("file_url").get(
                                                "content_type"
                                            ),
                                        }
                                    },
                                ]
                            )
                        else:
                            # try to convert ot text, if not possible sendo as bytes
                            try:
                                file_as_text = content_as_bytes.decode("utf-8")
                                parts.extend(
                                    [
                                        {
                                            "text": f"filename: {p.get('file_url').get('file_name')}"
                                        },
                                        {"text": file_as_text},
                                    ]
                                )
                            except UnicodeDecodeError:
                                parts.extend(
                                    [
                                        {
                                            "text": f"filename: {p.get('file_url').get('file_name')}"
                                        },
                                        {
                                            "inline_data": {
                                                "data": content_as_bytes,
                                                "mime_type": p.get("file_url").get(
                                                    "content_type"
                                                ),
                                            }
                                        },
                                    ]
                                )

                gemini_messages.append(
                    dict(
                        role="model" if m["role"] == ChatRole.assistant else "user",
                        parts=parts,
                    )
                )

        # ---
        print("Options: ", options)
        params = {
            "system_instruction": system_message,
        }
        if model_spec.has_image_generation and (options or {}).get(
            "use_image_generation"
        ):
            params["response_modalities"] = ["Text", "Image"]
        elif model_spec.is_image_model:
            params["response_modalities"] = ["Text", "Image"]
        else:
            params["response_modalities"] = ["Text"]
        if model_spec.has_web_search and (options or {}).get("use_search"):
            params["tools"] = [
                types.Tool(google_search=types.GoogleSearch()),
                types.Tool(url_context=types.UrlContext()),
            ]
        # if model_spec.has_url_context and (options or {}).get("use_url_context"):
        #     params['tools'] = [types.Tool(
        #         url_context=types.UrlContext()
        #     )]
        if options.get("response_json_schema"):
            params["response_mime_type"] = "application/json"
            params["response_json_schema"] = options.get("response_json_schema")
        # print('params: ', params)
        reasoning_effort = (options or {}).get(
            "reasoning_effort"
        ) or model_spec.reasoning_effort
        if reasoning_effort:
            params["thinking_config"] = types.ThinkingConfig(
                thinking_level=reasoning_effort
            )

        print("** params: ", {k: v for k, v in params.items() if k != "input"})

        print("CALL GEMINI >>>...")
        response = await self.client.aio.models.generate_content(
            model=model,
            contents=gemini_messages,
            config=types.GenerateContentConfig(**params),
        )
        print("CALL GEMINI >>>...DONE")

        # for debug. DON'T REMOVE
        debug_enabled = False
        if debug_enabled:
            tmp_file = Path(tempfile.gettempdir()) / (uuid.uuid4().hex + ".json")
            with tmp_file.open("w", encoding="utf-8") as f:
                json.dump(response.model_dump(), f, indent=2, cls=BytesEncoder)
            print(f"response written in {tmp_file}")

        response_d = response.model_dump()

        images = []
        try:
            for part in (
                response_d.get("candidates", [])[0].get("content", {}).get("parts", [])
            ):
                if part["text"] is not None:
                    continue
                    # answer.append(part['text'])
                elif part["inline_data"] is not None:
                    file_ext = part["inline_data"]["mime_type"].split("/")[-1]
                    filename = uuid.uuid4().hex + "." + file_ext
                    file_url = await S3UploadServices.upload_generate_image(
                        filename,
                        part["inline_data"]["data"],
                        file_ext,
                        FileCategory.GENERATED,
                    )
                    images.append(file_url)

                    # remove to dump for debug print out
                    part["inline_data"] = (
                        f"Image of size {len(part['inline_data']['data'])}"
                    )
            for f in temp_files:
                print("removing temp file ", f)
                os.remove(f)

            # print('GeminiLLM.achat: response:<<<', response_d)

            meta = response_d
            meta["elapsed_in_sec"] = time.time() - start_t
            meta["model"] = model

            meta["estimate_price"], meta["input_tokens"], meta["output_tokens"] = (
                calculate_estimate_price(model, meta["usage_metadata"])
            )
            meta["company"] = LLMNames.GEMINI.name
            # answer, meta['search_entry_point'] = answer_with_citations_if_exists(response)
            answer = response.text
            meta["grounding_list"] = get_grounding_list(response)
            UsageLogService.register_usage_meta(meta, LLMNames.GEMINI)
            return answer, images[0] if len(images) > 0 else None, None, meta
        except Exception as e:
            print(f"Error! {e}")
            traceback.print_exc()
            print("GeminiLLM.achat: response:<<<", response_d)
            raise

    effort_options = ["high", "medium", "low"]
    # -----
    # https://ai.google.dev/gemini-api/docs/pricing
    models: List[ModelDeclaration] = [
        ModelDeclaration(
            name="gemini-3-pro-preview",
            company=LLMNames.GEMINI,
            input_price=2.0,
            output_price=12.0,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#gemini-3-pro-preview",
            has_web_search=True,
            has_url_context=True,
            input_modality="TIAV",
            output_modality="T",
            effort_options=effort_options,
        ),
        ModelDeclaration(
            name="gemini-3-flash-preview",
            company=LLMNames.GEMINI,
            input_price=0.5,
            output_price=3.00,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#gemini-3-flash-preview",
            input_modality="TIAV",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gemini-3-pro-image-preview",
            description="aka nano banana pro",
            company=LLMNames.GEMINI,
            input_price=2.0,
            output_price=120.00,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#gemini-3-pro-image-preview",
            is_image_model=True,
            expensive=True,
            input_modality="TI",
            output_modality="TI",
        ),
        ModelDeclaration(
            name="gemini-2.5-pro",
            company=LLMNames.GEMINI,
            input_price=1.25,
            output_price=10.0,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-pro",
            has_web_search=True,
            has_url_context=True,
            input_modality="TIAV",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gemini-2.5-flash",
            company=LLMNames.GEMINI,
            input_price=0.30,
            output_price=2.50,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
            has_web_search=True,
            has_url_context=True,
            input_modality="TIAV",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gemini-2.5-flash-lite",
            company=LLMNames.GEMINI,
            input_price=0.1,
            output_price=0.4,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash-lite",
            has_web_search=True,
            has_url_context=True,
            input_modality="TIAV",
            output_modality="T",
        ),
        # ModelDeclaration(
        #     name="gemini-2.5-flash-lite-preview-06-17",
        #     company=LLMNames.GEMINI,
        #     input_price=0.30,
        #     output_price=0.40,
        #     max_token="1 million",
        #     eligible=True,
        #     is_vision_enabled=True,
        #     link="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-lite",
        #     has_web_search=True,
        # ),
        ModelDeclaration(
            name="gemini-2.5-flash-image-preview",
            description="aka nano banana",
            company=LLMNames.GEMINI,
            input_price=0.3,
            output_price=30.00,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash-image-preview",
            is_image_model=True,
            expensive=True,
            input_modality="TI",
            output_modality="TI",
        ),
        ModelDeclaration(
            name="gemini-2.0-flash-preview-image-generation",
            company=LLMNames.GEMINI,
            input_price=0.1,
            output_price=0.40,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.0-flash",
            is_image_model=True,
            input_modality="TI",
            output_modality="TI",
        ),
        # ModelDeclaration(
        #     name="gemini-2.0-flash-exp-image-generation",
        #     company=LLMNames.GEMINI,
        #     input_price=0.1,
        #     output_price=0.40,
        #     max_token="1 million",
        #     eligible=True,
        #     link="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.0-flash",
        #     is_image_model=True,
        #     input_modality = 'TI',
        #     output_modality = 'TI',
        # ),
        ModelDeclaration(
            name="gemini-2.0-flash-lite",
            company=LLMNames.GEMINI,
            input_price=0.075,
            output_price=0.30,
            max_token="1M",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#gemini-2.0-flash-lite",
            input_modality="TIAV",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gemma-3-27b-it",
            company=LLMNames.GEMINI,
            input_price=0.0,
            output_price=0.0,
            max_token="128k",
            eligible=True,
            link="https://ai.google.dev/gemini-api/docs/pricing#gemma-3",
            input_modality="TI",
            output_modality="T",
        ),
    ]
