import os
import time
import uuid
import base64
import tempfile
import traceback
from io import BytesIO
from pathlib import Path
from typing import List

from PIL import Image
from anthropic import AsyncAnthropic, NOT_GIVEN, APIStatusError

from .file_utils import download_file_as_byte
from ..services.s3_services import FileCategory
from .LLMBase import LLMBase
from .LLMModelDeclaration import LLMModelDeclaration
from .types.LLMNames import LLMNames
from .types.models import ModelDeclaration
from ..services.pricing import calculate_estimate_price
from ..services.s3_services import S3UploadServices
from ..services.usage_log_service import UsageLogService
from ..models.enums import ChatRole


class AnthropicLLM(LLMBase):
    def __init__(self):
        api_key = os.environ["ANTHROPIC_API_KEY"]
        self.client = AsyncAnthropic(api_key=api_key, timeout=600.0)  # 600 second

    async def achat(self, messages: list, model: str, options: dict = None):
        start_t = time.time()
        model_spec = LLMModelDeclaration.get_model(model)

        system_message = NOT_GIVEN
        if messages[0]["role"] == ChatRole.system:
            system_message = messages[0]["content"]
            messages = messages[1:]

        claude_messages = []
        for m in messages:
            role = "assistant" if m["role"] == ChatRole.assistant else "user"
            # message content: string or list of dicts (support image)
            if isinstance(m["content"], str):
                claude_messages.append(
                    {"role": role, "content": [{"type": "text", "text": m["content"]}]}
                )
            else:
                content_parts = []
                for p in m["content"]:
                    if p["type"] == "text":
                        content_parts.append({"type": "text", "text": p["text"]})
                    elif p["type"] == "image_url":
                        image_url = p["image_url"]["url"]
                        image_bytes = download_file_as_byte(image_url)
                        image = Image.open(BytesIO(image_bytes))
                        # Claude only supports JPEG/PNG/GIF (and only base64; not multipart)
                        mime_type = Image.MIME[image.format]
                        # anthropic expects base64 string, not bytes
                        payload = dict(
                            type="image",
                            source=dict(
                                type="base64",
                                media_type=mime_type,
                                data=base64.b64encode(image_bytes).decode("utf-8"),
                            ),
                        )
                        content_parts.append(payload)
                    elif p["type"] == "file_url":
                        file_url = p["file_url"]["url"]
                        content_type = p["file_url"]["content_type"]
                        content_as_bytes = download_file_as_byte(file_url)
                        if "pdf" in content_type or "image" in content_type:
                            content_parts.extend(
                                [
                                    {
                                        "type": "text",
                                        "text": f'filename: {p["file_url"]["file_name"]}',
                                    },
                                    {
                                        "type": (
                                            "document"
                                            if "pdf" in content_type
                                            else "image"
                                        ),
                                        "source": {
                                            "type": "base64",
                                            "media_type": content_type,
                                            "data": base64.b64encode(
                                                content_as_bytes
                                            ).decode("utf-8"),
                                        },
                                    },
                                ]
                            )
                        else:
                            # se não for pdf, tenta enviar como plain text
                            try:
                                file_as_text = content_as_bytes.decode("utf-8")
                                content_parts.extend(
                                    [
                                        {
                                            "type": "text",
                                            "text": f'filename: {p["file_url"]["file_name"]}',
                                        },
                                        {"type": "text", "text": file_as_text},
                                    ]
                                )
                            except UnicodeDecodeError:
                                # fallback, mas provavelmente vai recusar
                                print(
                                    "Entrou em fallback: ",
                                    p["file_url"]["file_name"],
                                    content_type,
                                )
                                content_parts.extend(
                                    [
                                        {
                                            "type": "text",
                                            "text": f'filename: {p["file_url"]["file_name"]}',
                                        },
                                        {
                                            "type": "document",
                                            "source": {
                                                "type": "base64",
                                                "media_type": content_type,
                                                "data": base64.b64encode(
                                                    content_as_bytes
                                                ).decode("utf-8"),
                                            },
                                        },
                                    ]
                                )

                claude_messages.append({"role": role, "content": content_parts})

        # Anthropic supports a top-level "system" string, not as a user message
        try:
            # print( f"Anthropic>>>. system_message = {system_message}")
            print(f"Anthropic>>>. messages = {claude_messages[-1]}")
            response = await self.client.messages.create(
                model=model,
                messages=claude_messages,
                system=system_message,
                max_tokens=(
                    4096
                    if not model_spec.max_output_tokens
                    else model_spec.max_output_tokens
                ),
            )
        except APIStatusError as e:
            raise Exception(f"Anthropic API error: {e}")

        # Extract text (Claude API: response.content is a list of blocks, each with "type" and maybe "text" or "source")
        answer = []
        images = []
        response = response.model_dump()
        print(f"Anthropic <<<:\n{response}")

        for part in response["content"]:
            if part["type"] == "text":
                answer.append(part["text"])
            elif part["type"] == "image":
                # Save image to S3 and get URL
                image_base64 = part["source"].get("data")
                mime_type = part["source"]["media_type"]
                file_ext = mime_type.split("/")[-1]
                filename = uuid.uuid4().hex + "." + file_ext
                image_bytes = base64.b64decode(image_base64)
                file_url = await S3UploadServices.upload_generate_image(
                    filename, image_bytes, file_ext, FileCategory.GENERATED
                )
                images.append(file_url)

        meta = {
            **response,
            "elapsed_in_sec": time.time() - start_t,
            "model": model,
        }
        # try:
        #     meta['usage'] = { **response['usage'],
        #         "prompt_tokens": response['usage']['input_tokens'],
        #         "completion_tokens": response['usage']['output_tokens'],
        #         "total_tokens": response.get('usage').get('input_tokens') + response.get('usage').get('output_tokens'),
        #     }
        #     meta['estimate_price'], meta['input_token'], meta['output_token'] = calculate_estimate_price(model, meta['usage'])
        # except Exception as e:
        #     print("Error calculating price, assume 0", e)
        #     traceback.print_exc()
        #     meta['estimate_price'] = 0
        meta["estimate_price"], meta["input_tokens"], meta["output_tokens"] = (
            calculate_estimate_price(model, meta["usage"])
        )
        meta["company"] = LLMNames.ANTHROPIC.name
        UsageLogService.register_usage_meta(meta, LLMNames.ANTHROPIC)

        return " ".join(answer), images[0] if images else None, None, meta

    # async def achat_json(self, messages, model: str):
    #     raise Exception("Not implemented")

    # async def generate_image(self, prompt: str, model: str):
    #     raise Exception("Not implemented")

    models: List[ModelDeclaration] = [
        ModelDeclaration(
            name="claude-opus-4-5-20251101",
            company=LLMNames.ANTHROPIC,
            input_price=5.0,
            output_price=25.0,
            max_token="200 k",
            max_output_tokens=64000,
            eligible=True,
            input_modality="TI",
            output_modality="T",
            link="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelDeclaration(
            name="claude-sonnet-4-5-20250929",
            company=LLMNames.ANTHROPIC,
            input_price=3.0,
            output_price=15.0,
            max_token="200 k",
            max_output_tokens=64000,
            eligible=True,
            input_modality="TI",
            output_modality="T",
            link="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelDeclaration(
            name="claude-haiku-4-5-20251001",
            company=LLMNames.ANTHROPIC,
            input_price=1.0,
            output_price=5.00,
            max_token="200 k",
            max_output_tokens=64000,
            eligible=True,
            input_modality="TI",
            output_modality="T",
            link="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelDeclaration(
            name="claude-opus-4-1-20250805",
            company=LLMNames.ANTHROPIC,
            input_price=15.0,
            output_price=75.0,
            max_token="200 k",
            max_output_tokens=32000,
            eligible=True,
            expensive=True,
            link="https://docs.anthropic.com/en/docs/about-claude/models/overview",
            input_modality="TI",
            output_modality="T",
        ),
        # ModelDeclaration(
        #     name="claude-opus-4-20250514",
        #     company=LLMNames.ANTHROPIC,
        #     input_price=15.0,
        #     output_price=75.0,
        #     max_token="200 k",
        #     max_output_tokens=32000,
        #     eligible=True,
        #     expensive=True,
        #     input_modality = 'TI',
        #     output_modality = 'T',
        #     link="https://docs.anthropic.com/en/docs/about-claude/models/overview"
        # ),
        ModelDeclaration(
            name="claude-sonnet-4-20250514",
            company=LLMNames.ANTHROPIC,
            input_price=3.0,
            output_price=15.0,
            max_token="200 k",
            max_output_tokens=64000,
            eligible=True,
            input_modality="TI",
            output_modality="T",
            link="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelDeclaration(
            name="claude-3-5-haiku-20241022",
            company=LLMNames.ANTHROPIC,
            input_price=0.8,
            output_price=4.0,
            max_token="200 k",
            max_output_tokens=8192,
            eligible=True,
            input_modality="TI",
            output_modality="T",
            link="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
        ModelDeclaration(
            name="claude-3-7-sonnet-20250219",
            company=LLMNames.ANTHROPIC,
            input_price=3.0,
            output_price=15.0,
            max_token="200 k",
            max_output_tokens=8192,
            eligible=False,
            input_modality="TI",
            output_modality="T",
            link="https://docs.anthropic.com/en/docs/about-claude/models/overview",
        ),
    ]
