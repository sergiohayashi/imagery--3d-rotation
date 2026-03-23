from __future__ import annotations

import base64
import json
import os
import tempfile
import time
import traceback
import uuid
from pathlib import Path
from typing import List, Union

from openai import NOT_GIVEN
import openai

from app.services.pdf_services import FileService

from .LLMBase import LLMBase
from .LLMModelDeclaration import LLMModelDeclaration
from .encoder_helper import BytesEncoder
from .file_utils import download_file_as_base64, download_file_as_byte, download_to_temp
from .types.LLMNames import LLMNames
from .types.models import ModelDeclaration
from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage
from ..models.file_category import FileCategory
from ..services.pricing import calculate_estimate_price
from ..services.s3_services import S3UploadServices
from ..services.usage_log_service import UsageLogService
from ..utils.file_utils import guess_content_type_from_filename


xai_api_key = os.getenv("XAI_API_KEY")
xai_base_url = "https://api.x.ai/v1"


def save_to_tmp(tag, data):
    tmp_file = Path(tempfile.gettempdir()) / (f"{tag}-" + uuid.uuid4().hex + ".txt")
    with tmp_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, cls=BytesEncoder)
    print(f"tmp data of tag {tag} written to {tmp_file}")


def parse_json_response(response):
    json_response = response.output_text
    json_response = json_response.replace("```json", "").replace("```", "").strip()
    try:
        parse_json = json.loads(json_response, strict=False)
    except Exception as e:
        print(f"Error parsing json string: type(e)={type(e)}. Error occurred: {e}")
        traceback.print_exc()
        parse_json = response.output_text

    return parse_json


markdown_instruction = "Formatting re-enabled"
markdown_instruction_4o_latest = "Format your response using proper markup and code formatting where applicable. For example, use Markdown for headings, lists, and inline code, and format code blocks with appropriate syntax highlighting. Ensure that all code snippets are enclosed in triple backticks (```) with the correct language specified for clarity"
markdown_instruction_enhanced = "Formatting re-enabled. Format your response using proper markup and code formatting where applicable. For example, use Markdown for headings, lists, and inline code, and format code blocks with appropriate syntax highlighting. Ensure that all code snippets are enclosed in triple backticks (```) with the correct language specified for clarity"
markdown_instruction_enhanced_with_math = "Formatting re-enabled. Format your response using proper markup and code formatting where applicable. For example, use Markdown for headings, lists, and inline code, and format code blocks with appropriate syntax highlighting. Ensure that all code snippets are enclosed in triple backticks (```) with the correct language specified. For math notation use TeX/LaTeX math-mode delimiters."


class MyTest:
    pass


def maybe_text(content, content_type=None):
    """
    Try to interpret the given content as text if its type suggests it is text.

    Parameters:
      content: either bytes or a string.
               - If it is a bytes object, we attempt to decode it.
               - If it is a str, we first try to see if it looks like base64,
                 and if so, decode that (otherwise assume it's already text).
      content_type (str, optional): a MIME type (e.g. "text/plain", "application/json")
               or file extension (e.g. ".txt", ".json") that hints at a text file.

    Returns:
      The decoded text (usually assuming UTF-8) if this looks like a text file,
      or None if it appears to be binary or if decoding fails.
    """

    def is_text_type(ct):
        """Determine if the provided content_type hints at a text file."""
        if not ct:
            return False
        ct = ct.lower().strip()
        # If it starts with "text/", it is text.
        if ct.startswith("text/"):
            return True

        # Check for common JSON, YAML, XML, CSV, or HTML identifiers.
        for substr in ["json", "yaml", "xml", "csv", "html"]:
            if substr in ct:
                return True

        # If it's just a file extension, compare against a set of known text extensions.
        if ct.startswith("."):
            known_extensions = {
                ".txt",
                ".json",
                ".yaml",
                ".yml",
                ".md",
                ".csv",
                ".html",
                ".htm",
                ".xml",
            }
            if ct in known_extensions:
                return True

        return False

    # At this point, content should be a bytes object.
    # If a content_type was provided, check if it looks like a text type.
    if is_text_type(content_type):
        return True

    # Try to decode the bytes using UTF-8.
    try:
        _ = content.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


async def get_container_file_and_upload_to_s3(container_id, file_id, file_name):
    import requests

    url = f"{xai_base_url}/containers/{container_id}/files/{file_id}/content"
    headers = {
        "Authorization": f"Bearer {xai_api_key}",
    }
    print("Downloading generated file from: ", url)
    response = requests.get(url, headers=headers)
    data = response.content

    file_url = await S3UploadServices.upload_generate_file(
        file_name, data, FileCategory.GENERATED
    )
    return file_url


async def upload_generated_base64_image_to_s3(
    file_name: str, base64_data, file_extension: str
):
    file_url = await S3UploadServices.upload_generate_image(
        file_name, base64.b64decode(base64_data), file_extension, FileCategory.GENERATED
    )
    return file_url


def _get_async_client():
    return openai.AsyncOpenAI(api_key=xai_api_key, base_url=xai_base_url)


def _get_client():
    return openai.OpenAI(api_key=xai_api_key, base_url=xai_base_url)


class xAILLM_ResponseApiStream(LLMBase):

    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model: str,
        options: dict = None,
    ) -> (dict | str, OpBoostChatCompletion):
        start_t = time.time()

        print("XAILLM.achat: message[-1]:>>>", messages[-1])
        # print('OpenAILLM.achat: message:>>>', messages)
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
            is_assistant = m.get("role") == "assistant"
            if isinstance(m["content"], str):
                if m.get("content"):
                    messages_to_send.append(
                        {"role": m.get("role"), "content": m.get("content")}
                    )
            else:
                _contents = []
                _send_as_user_content = []
                is_user = m.get("role" == "user")
                for p in m["content"]:
                    if p["type"] == "text":
                        if not p.get("text") or p.get("text") == "(empty)":
                            continue
                        _contents.append(
                            {
                                "type": "input_text" if is_user else "output_text",
                                "text": p.get("text"),
                            }
                        )
                    elif p["type"] == "image_url":
                        _file = p.get("image_url")
                        if _file.get("url").startswith("http"):
                            _send_as_user_content.append(
                                {"type": "input_image", "image_url": _file.get("url")}
                            )
                        else:
                            file_as_base64 = download_file_as_base64(_file.get("url"))
                            _send_as_user_content.extend(
                                [
                                    {
                                        "type": "input_file",
                                        "filename": Path(_file.get("url")).name,
                                        "file_data": f'data:{guess_content_type_from_filename(_file.get("url"))};base64,{file_as_base64}',
                                    }
                                ]
                            )
                    elif p["type"] == "file_url":
                        _file = p.get("file_url")
                        print(f"file: {p.get('file_url')}")
                        if "image" in _file.get("content_type"):
                            if _file.get("url").startswith("http"):
                                _send_as_user_content.extend(
                                    [
                                        {
                                            "type": "input_text",
                                            "text": f"filename: {_file.get('file_name')}",
                                        },
                                        {
                                            "type": "input_image",
                                            "image_url": _file.get("url"),
                                        },
                                    ]
                                )
                            else:  # file://
                                file_as_base64 = download_file_as_base64(
                                    _file.get("url")
                                )
                                _send_as_user_content.extend(
                                    [
                                        {
                                            "type": "input_file",
                                            "filename": _file.get("file_name"),
                                            "file_data": f'data:{_file.get("content_type")};base64,{file_as_base64}',
                                        }
                                    ]
                                )
                        elif "pdf" in _file.get("content_type"):
                            file_as_base64 = download_file_as_base64(_file.get("url"))
                            _send_as_user_content.extend(
                                [
                                    {
                                        "type": "input_file",
                                        "filename": _file.get("file_name"),
                                        "file_data": f'data:{_file.get("content_type")};base64,{file_as_base64}',
                                    }
                                ]
                            )

                        elif _file.get("file_name").endswith(".xlsx"):
                            file_as_text = FileService.extract_data_from_xlsx(
                                download_to_temp(_file.get("url"))
                            )
                            _send_as_user_content.extend(
                                [
                                    {
                                        "type": "input_text",
                                        "text": f"filename: {_file.get('file_name')}. File content(text format): \n```{file_as_text}```",
                                    },
                                ]
                            )
                        else:
                            content_as_bytes = download_file_as_byte(_file.get("url"))
                            try:
                                file_as_text = content_as_bytes.decode("utf-8")
                                _send_as_user_content.extend(
                                    [
                                        {
                                            "type": "input_text",
                                            "text": f"filename: {_file.get('file_name')}. File content: \n```{file_as_text}```",
                                        },
                                    ]
                                )
                                print(
                                    f"send {_file.get('file_name')} as text with content: ```{file_as_text[:100]}...```"
                                )
                            except UnicodeDecodeError:
                                file_as_base64 = base64.b64encode(
                                    content_as_bytes
                                ).decode("utf-8")
                                print(f"send {_file.get('file_name')} as file(base64)")
                                _send_as_user_content.extend(
                                    [
                                        # {
                                        #     "type": "input_text",
                                        #     "text": f"filename: {_file.get('file_name')}",
                                        # },
                                        {
                                            "type": "input_file",
                                            "filename": _file.get("file_name"),
                                            "file_data": f'data:{_file.get("content_type")};base64,{file_as_base64}',
                                        },
                                    ]
                                )
                    else:
                        pass  # don't happen

                if _contents:
                    messages_to_send.append(
                        {"role": m.get("role"), "content": _contents}
                    )
                if _send_as_user_content:
                    messages_to_send.append(
                        {"role": "user", "content": _send_as_user_content}
                    )

        # print('messages:\n-----', messages_to_send, '\n-------\n')
        # save_to_tmp("original-message", messages)
        # save_to_tmp("converted-message", messages_to_send)
        if os.getenv("ENV") == "dev-x":
            print("messages_to_send:>>>")
            for m in messages_to_send:
                print("-------\n", json.dumps(m, indent=2, cls=BytesEncoder))
            # print('messages_to_send:<<<')

        params = {
            "model": model,
            "input": messages_to_send,
            "store": False,
        }

        reasoning_effort = (options or {}).get(
            "reasoning_effort"
        ) or model_spec.reasoning_effort
        if reasoning_effort:
            params["reasoning"] = {"effort": reasoning_effort}
        tools = []
        includes = []

        if model_spec.has_web_search and (options or {}).get("use_search"):
            tools.append({"type": "web_search_preview"})
            print("use web-search")
        if model_spec.has_code_interpreter and (options or {}).get("use_code"):
            tools.append({"type": "code_interpreter", "container": {"type": "auto"}})
            includes.append("code_interpreter_call.outputs")
            print("use code interpreter")
        if model_spec.has_image_generation and (options or {}).get(
            "use_image_generation"
        ):
            tools.append({"type": "image_generation"})
            print("use image generation")

        if tools:
            params["tools"] = tools
        if includes:
            params["include"] = includes
        if "temperature" in (options or {}):
            params["temperature"] = (options or {}).get("temperature")

        print("** params: ", {k: v for k, v in params.items() if k != "input"})
        try:
            # call as stream void timeout, and don't affect performance, actually improve
            # so, even thought the app don't handle streaming, call the api with this option
            async with _get_async_client().responses.stream(**params) as stream:
                async for event in stream:
                    pass
                    # if event.type == "response.output_text.delta":
                    #     print(event.delta, end="", flush=True)
                    # # (Optional) Image/file events arrive in one shot when ready
                    # elif event.type == "response.output_image.image":
                    #     print("\n[image saved: out.png]")
                    #     # img_b64 = event.image_b64  # SDK provides base64 for the image
                    #     # with open("out.png", "wb") as f:
                    #     #     f.write(base64.b64decode(img_b64))
                    #     # print("\n[image saved: out.png]")
                    #
                    # elif event.type == "response.output_file":
                    #     print(f"\n[file ready: {event.file.url}]")
                    #
                    # elif event.type == "response.error":
                    #     print("\n[stream error]", event.error)
                    #
                    # # else:
                    # #     print(f"[{event.type}]", event)

                response = await stream.get_final_response()

            # print('XAILLM.achat: response:<<<', response)
            # UsageLogService.register_usage(response)
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            save_to_tmp("original-message", messages)
            save_to_tmp("converted-message", messages_to_send)
            raise

        # for debug. DON'T REMOVE
        debug_enabled = False
        if debug_enabled:
            tmp_file = Path(tempfile.gettempdir()) / (
                "xai-" + uuid.uuid4().hex + ".json"
            )
            with tmp_file.open("w", encoding="utf-8") as f:
                json.dump(response.model_dump(), f, indent=2, cls=BytesEncoder)
            print(f"response written in {tmp_file}")

        url_citations = {}
        texts: List[str] = []
        files = []
        code_interpreter_container_use, has_image_generator_use = 0, False
        containers = set()
        response_obj = response.model_dump()
        images = []
        # output_files = set()
        for output in response_obj.get("output"):
            if output.get("type") == "code_interpreter_call":
                code_interpreter_container_use = 1
                containers.add(output.get("container_id"))

            elif output.get("type") == "image_generation_call":
                has_image_generator_use = True

                file_extension = output.get("output_format")
                file_name = f"{uuid.uuid4().hex}.{file_extension}"
                images.append(
                    await upload_generated_base64_image_to_s3(
                        file_name, output.get("result"), output.get("output_format")
                    )
                )

                # remove to reduce log size
                output["result"] = f"Image... of size {len(output.get('result'))}"

            elif (
                output.get("type") == "message"
            ):  # "reasoning", "code_interpreter_call", ..
                for content in output.get("content"):
                    if content.get("type") == "output_text":  # output_text,

                        # collect the text..
                        texts.append(content.get("text"))

                        # ref: https://platform.openai.com/docs/api-reference/responses/object
                        for c in content.get("annotations", []):
                            if (
                                c["type"] == "url_citation"
                            ):  # "url_citation", file_citation, container_file_citation, file_path
                                url_citations[c["url"]] = c["title"]

                            elif c["type"] == "file_citation":
                                print("Received file_citation. Ignore..: ", c)

                            elif c["type"] == "container_file_citation":
                                print("File received: ", c)
                                # output_files.add((c['file_id'], c['container_id'], c['filename']))
                                files.append(
                                    {
                                        "file_url": await get_container_file_and_upload_to_s3(
                                            c["container_id"],
                                            c["file_id"],
                                            c["filename"],
                                        ),
                                        "file_name": c["filename"],
                                        "content_type": guess_content_type_from_filename(
                                            c["filename"]
                                        ),
                                    }
                                )

                            elif c["type"] == "file_path":
                                print("Received file_path. Ignore..: ", c)

        answer = "".join(texts)

        print("XAILLM.achat: response:<<<", response_obj)

        meta = response_obj
        meta["elapsed_in_sec"] = time.time() - start_t
        # meta['estimate_price'] = calculate_estimate_price(model, meta.get('usage'))
        meta["estimate_price"], meta["input_tokens"], meta["output_tokens"] = (
            calculate_estimate_price(model, meta["usage"], len(containers))
        )
        meta["usage"]["code_interpreter_container_use"] = len(containers)
        meta["company"] = LLMNames.XAI.name
        # https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses
        # openai diz que tem que pôr as citações no meio do texto para cada trecho.
        if url_citations:
            meta["grounding_list"] = [
                {"title": value, "uri": key} for key, value in url_citations.items()
            ]
        UsageLogService.register_usage_meta(meta, LLMNames.XAI)
        return (
            answer,
            images[0] if len(images) > 0 else None,
            None if len(files) <= 0 else files,
            meta,
        )

    # -----
    effort_options_with_minimal = ["high", "medium", "low", "minimal"]
    effort_options_with_none = ["high", "medium", "low", "none"]
    effort_options = ["high", "medium", "low"]
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
    ]
