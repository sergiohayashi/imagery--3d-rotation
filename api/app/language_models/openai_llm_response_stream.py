from __future__ import annotations

import base64
import json
import logging
import tempfile
import time
import traceback
import uuid
from pathlib import Path
from typing import List, Union

from openai import NOT_GIVEN

from . import openai_commons
from .LLMBase import LLMBase
from .LLMModelDeclaration import LLMModelDeclaration
from .encoder_helper import BytesEncoder
from .file_utils import download_file_as_base64, download_file_as_byte
from .openai_commons import get_async_client
from .types.LLMNames import LLMNames
from .types.models import ModelDeclaration
from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage
from ..models.file_category import FileCategory
from ..services.pricing import calculate_estimate_price
from ..services.s3_services import S3UploadServices
from ..services.usage_log_service import UsageLogService
from ..utils.file_utils import guess_content_type_from_filename


def save_to_tmp(tag, data):
    tmp_file = Path(tempfile.gettempdir()) / (f"{tag}-" + uuid.uuid4().hex + ".txt")
    with tmp_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, cls=BytesEncoder)
    print(f"tmp data of tag {tag} written to {tmp_file}")


markdown_instruction = "Formatting re-enabled"
markdown_instruction_4o_latest = "Format your response using proper markup and code formatting where applicable. For example, use Markdown for headings, lists, and inline code, and format code blocks with appropriate syntax highlighting. Ensure that all code snippets are enclosed in triple backticks (```) with the correct language specified for clarity"
markdown_instruction_enhanced = "Formatting re-enabled. Format your response using proper markup and code formatting where applicable. For example, use Markdown for headings, lists, and inline code, and format code blocks with appropriate syntax highlighting. Ensure that all code snippets are enclosed in triple backticks (```) with the correct language specified for clarity"
markdown_instruction_enhanced_with_math = "Formatting re-enabled. Format your response using proper markup and code formatting where applicable. For example, use Markdown for headings, lists, and inline code, and format code blocks with appropriate syntax highlighting. Ensure that all code snippets are enclosed in triple backticks (```) with the correct language specified. For math notation use TeX/LaTeX math-mode delimiters."


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

    url = f"https://api.openai.com/v1/containers/{container_id}/files/{file_id}/content"
    headers = {
        "Authorization": f"Bearer {openai_commons.get_api_key()}",
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


class OpenAILLM_ResponseApiStream(LLMBase):

    async def achat(
        self,
        messages: Union[list[OpBoostChatMessage], list[dict]],
        model: str,
        options: dict = None,
    ) -> (dict | str, OpBoostChatCompletion):
        start_t = time.time()

        print("OpenAILLM_ResponseApiStream called with model=", model)
        # print('OpenAILLM.achat: message[-1]:>>>', messages[-1])
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
                        else:  # file://
                            content_type = guess_content_type_from_filename(
                                _file.get("url")
                            )
                            print(
                                f"Sending image as base64. content_type:{content_type} url: {_file.get('url')}"
                            )
                            file_as_base64 = download_file_as_base64(_file.get("url"))
                            _send_as_user_content.extend(
                                [
                                    {
                                        "type": "input_image",
                                        "image_url": f"data:{content_type};base64,{file_as_base64}",
                                    }
                                ]
                            )
                    elif p["type"] == "file_url":
                        _file = p.get("file_url")
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
                                print(
                                    f"Sending image as base64. content_type:{_file.get('content_type', 'image/png')} url: {_file.get('url')}"
                                )
                                content_type = guess_content_type_from_filename(
                                    _file.get("url")
                                )
                                file_as_base64 = download_file_as_base64(
                                    _file.get("url")
                                )
                                _send_as_user_content.extend(
                                    [
                                        {
                                            "type": "input_image",
                                            "image_url": f"data:{content_type};base64,{file_as_base64}",
                                        }
                                    ]
                                )

                        elif "pdf" in _file.get("content_type"):
                            file_as_base64 = download_file_as_base64(_file.get("url"))
                            _send_as_user_content.extend(
                                [
                                    {
                                        #     "type": "input_text",
                                        #     "text": f"filename: {_file.get('file_name')}"
                                        # }, {
                                        "type": "input_file",
                                        "filename": _file.get("file_name"),
                                        "file_data": f'data:{_file.get("content_type")};base64,{file_as_base64}',
                                    }
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
                                            "text": f"filename: {_file.get('file_name')}",
                                        },
                                        {"type": "input_text", "text": file_as_text},
                                    ]
                                )
                                print(f"send {_file.get('file_name')} as text")
                            except UnicodeDecodeError:
                                file_as_base64 = base64.b64encode(
                                    content_as_bytes
                                ).decode("utf-8")
                                print(f"send {_file.get('file_name')} as file(base64)")
                                _send_as_user_content.extend(
                                    [
                                        {
                                            "type": "input_text",
                                            "text": f"filename: {_file.get('file_name')}",
                                        },
                                        {
                                            "type": "input_file",
                                            "filename": _file.get("file_name"),
                                            "file_data": f'data:{_file.get("content_type")};base64,{file_as_base64}',
                                        },
                                    ]
                                )
                    else:
                        pass  # don't happen

                messages_to_send.append({"role": m.get("role"), "content": _contents})
                if _send_as_user_content:
                    messages_to_send.append(
                        {"role": "user", "content": _send_as_user_content}
                    )

        # remove blank
        messages_to_send = [
            m for m in messages_to_send if m.get("content") not in ["", [], None]
        ]
        # DEBUG
        # print('\n========================================\n')
        # for m in messages_to_send:
        #     print(f'{json.dumps(m)}\n----\n')
        # print('\n========================================\n')
        # print('messages:\n-----', messages_to_send, '\n-------\n')
        # save_to_tmp("original-message", messages)
        # save_to_tmp("converted-message", messages_to_send)

        params = {
            "model": model,
            "input": messages_to_send,
            "store": False,
            # "temperature": 0.0, #deterministic
            # "top_p": 1, #deterministic
            # "seed": 42, #deterministic
        }

        # if "response_format" in options:
        #     params["response_format"]= { type: "json_object" }

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
            tools.append(
                {
                    "type": "image_generation",
                    **options.get("use_image_generation__options", {}),
                }
            )
            print("use image generation")

        if tools:
            params["tools"] = tools
        if includes:
            params["include"] = includes
        # if "temperature" in (options or {}):
        #     params["temperature"] = (options or {}).get("temperature")

        print("** params: ", {k: v for k, v in params.items() if k != "input"})

        # try:
        #     response = await get_async_client().responses.create(**params)
        #     # print('OpenAILLM.achat: response:<<<', response)
        #     # UsageLogService.register_usage(response)
        # except Exception as e:
        #     print( f"Error: {e}")
        #     traceback.print_exc()
        #     save_to_tmp("original-message", messages)
        #     save_to_tmp("converted-message", messages_to_send)
        #     raise

        try:
            # call as stream void timeout, and don't affect performance, actually improve
            # so, even thought the app don't handle streaming, call the api with this option
            async with get_async_client().responses.stream(**params) as stream:
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

            # print('OpenAILLM.achat: response:<<<', response)
            # UsageLogService.register_usage(response)
        except Exception as e:
            # logging.exception( f"Error in OpenAILLM_ResponseApiStream.achat: {e}")
            # traceback.print_exc()
            # save_to_tmp("original-message", messages)
            # save_to_tmp("converted-message", messages_to_send)
            raise

        # for debug. DON'T REMOVE
        debug_enabled = False
        if debug_enabled:
            tmp_file = Path(tempfile.gettempdir()) / (
                "openai-" + uuid.uuid4().hex + ".json"
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

                # NOTE 20250827: o code interpreter pode gerar corretamente o arquivo, mas nem sempre a api consegue
                # trazer de volta corretamente o arquivo. Isso parece ser ainda uma limitação da api da openai,
                # principalmente quando tem mais de um arquivo de saida.
                # ---
                # _files = await get_async_client().containers.files.list(container_id=output.get('container_id'))
                # for f in _files.data:
                #     print(f'** CONTAINER FILES ** {f.id} {output.get("container_id")} ', f)
                #     output_files.add((f.id, output.get("container_id"), (f.path or 'noname').split()[0]))

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
        # answer = response.output_text
        # print( "*** OUTPUT FILES ***: ")
        # for _file_id, _container, _file_name in output_files:
        #     print("> ", _container, _file_id, _file_name)
        #     files.append({
        #         "file_url": await get_container_file_and_upload_to_s3(
        #             _container, _file_id, _file_name
        #         ),
        #         "file_name": _file_name,
        #         "content_type": guess_content_type_from_filename(_file_name)
        #     })

        # print('OpenAILLM.achat: response:<<<', response_obj)

        meta = response_obj
        meta["elapsed_in_sec"] = time.time() - start_t
        # meta['estimate_price'] = calculate_estimate_price(model, meta.get('usage'))
        meta["estimate_price"], meta["input_tokens"], meta["output_tokens"] = (
            calculate_estimate_price(model, meta["usage"], len(containers))
        )
        meta["usage"]["code_interpreter_container_use"] = len(containers)
        meta["company"] = LLMNames.OPENAI.name
        # https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses
        # openai diz que tem que pôr as citações no meio do texto para cada trecho.
        if url_citations:
            meta["grounding_list"] = [
                {"title": value, "uri": key} for key, value in url_citations.items()
            ]
        UsageLogService.register_usage_meta(meta, LLMNames.OPENAI)
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
            name="gpt-5.4-2026-03-05",
            company=LLMNames.OPENAI,
            input_price=2.50,
            output_price=15,
            eligible=True,
            max_token="1M",
            has_web_search=True,
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            has_image_generation=True,
            link="https://platform.openai.com/docs/models/gpt-5.4",
            input_modality="TI",
            output_modality="T",
            # reasoning_effort = 'high',
            effort_options=effort_options_with_none,
        ),
        ModelDeclaration(
            name="gpt-5.2-chat-latest",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            max_token="128k",
            has_web_search=False,
            has_code_interpreter=False,
            has_image_generation=False,
            link="https://platform.openai.com/docs/models/gpt-5.1-chat-latest",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gpt-5.2",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            max_token="400k",
            has_web_search=True,
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            has_image_generation=True,
            link="https://platform.openai.com/docs/models/gpt-5.1",
            input_modality="TI",
            output_modality="T",
            # reasoning_effort = 'high',
            effort_options=effort_options_with_none,
        ),
        ModelDeclaration(
            name="gpt-5.2-2025-12-11",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            max_token="400k",
            has_web_search=True,
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            has_image_generation=True,
            link="https://platform.openai.com/docs/models/gpt-5.1",
            input_modality="TI",
            output_modality="T",
            # reasoning_effort = 'high',
            effort_options=effort_options_with_none,
        ),
        ModelDeclaration(
            name="gpt-5.1-chat-latest",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            max_token="128k",
            has_web_search=False,
            has_code_interpreter=False,
            has_image_generation=False,
            link="https://platform.openai.com/docs/models/gpt-5.1-chat-latest",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gpt-5.1",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            max_token="400k",
            has_web_search=True,
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            has_image_generation=True,
            link="https://platform.openai.com/docs/models/gpt-5.1",
            input_modality="TI",
            output_modality="T",
            # reasoning_effort = 'high',
            effort_options=effort_options_with_none,
        ),
        ModelDeclaration(
            name="gpt-5.1-codex",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            max_token="400k",
            has_web_search=False,
            has_code_interpreter=False,
            has_image_generation=True,
            link="https://platform.openai.com/docs/models/gpt-5.1-codex",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gpt-5.1-codex-mini",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            max_token="400k",
            has_web_search=False,
            has_code_interpreter=False,
            has_image_generation=True,
            link="https://platform.openai.com/docs/models/gpt-5.1-codex-mini",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gpt-5-chat-latest",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            max_token="128k",
            has_web_search=True,
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            has_image_generation=True,
            link="https://platform.openai.com/docs/models/gpt-5-chat-latest",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gpt-5",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            reasoning_effort="low",
            # reasoning_effort = 'minimal',   # high make slow
            max_token="400k",
            has_web_search=True,
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            has_image_generation=True,
            force_system_message_to_inject=markdown_instruction_enhanced_with_math,
            link="https://platform.openai.com/docs/models/gpt-5",
            input_modality="TI",
            output_modality="T",
            effort_options=effort_options_with_minimal,
        ),
        ModelDeclaration(
            name="gpt-5-codex",
            company=LLMNames.OPENAI,
            input_price=1.25,
            output_price=10,
            eligible=True,
            # reasoning_effort = 'high',
            max_token="400k",
            # has_web_search=True,
            # has_code_interpreter=True,
            # code_interpreter_price_per_container=0.03,
            # has_image_generation=True,
            # force_system_message_to_inject = markdown_instruction_enhanced_with_math,
            link="https://platform.openai.com/docs/models/gpt-5-codex",
            input_modality="TI",
            output_modality="T",
            effort_options=effort_options_with_minimal,
        ),
        # ModelDeclaration(
        #     name="gpt-5-pro-2025-10-06",
        #     company=LLMNames.OPENAI,
        #     input_price=15,
        #     output_price=120,
        #     eligible=True,
        #     expensive=True,
        #     reasoning_effort = 'low',
        #     # reasoning_effort = 'minimal',   # high make slow
        #     # reasoning_effort = 'high',
        #     max_token="400k",
        #     has_web_search=True,
        #     # has_code_interpreter=True,
        #     # code_interpreter_price_per_container=0.03,
        #     has_image_generation=True,
        #     # force_system_message_to_inject = markdown_instruction_enhanced_with_math,
        #     link="https://platform.openai.com/docs/models/gpt-5-pro",
        #     input_modality = 'TI',
        #     output_modality = 'T',
        #     # effort_options = effort_options_with_minimal,
        # ),
        ModelDeclaration(
            name="gpt-5-mini",
            company=LLMNames.OPENAI,
            input_price=0.25,
            output_price=2,
            eligible=True,
            # reasoning_effort = 'low',
            # reasoning_effort = 'minimal',   # high make slow
            max_token="400k",
            has_web_search=True,
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            force_system_message_to_inject=markdown_instruction_enhanced_with_math,
            link="https://platform.openai.com/docs/models/gpt-5-mini",
            input_modality="TI",
            output_modality="T",
            effort_options=effort_options_with_minimal,
        ),
        ModelDeclaration(
            name="gpt-5-nano",
            company=LLMNames.OPENAI,
            input_price=0.05,
            output_price=0.4,
            reasoning_effort="minimal",  # high make slow
            # reasoning_effort = 'minimal',
            eligible=True,
            max_token="400k",
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            has_image_generation=True,
            force_system_message_to_inject=markdown_instruction_enhanced_with_math,
            link="https://platform.openai.com/docs/models/gpt-5-nano",
            input_modality="TI",
            output_modality="T",
            effort_options=effort_options_with_minimal,
        ),
        ModelDeclaration(
            name="chatgpt-4o-latest",
            company=LLMNames.OPENAI,
            # description="Improved for chat",
            input_price=5,
            output_price=15,
            eligible=True,
            max_token="128k",
            force_system_message_to_inject=markdown_instruction_4o_latest,
            link="https://platform.openai.com/docs/models/chatgpt-4o-latest",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="gpt-4.1",
            company=LLMNames.OPENAI,
            input_price=2,
            output_price=8.0,
            eligible=True,
            max_token="1M",
            has_web_search=True,
            has_code_interpreter=True,
            code_interpreter_price_per_container=0.03,
            has_image_generation=True,
            link="https://platform.openai.com/docs/models/gpt-4.1",
            input_modality="TI",
            output_modality="T",
        ),
        ModelDeclaration(
            name="o3-pro",
            company=LLMNames.OPENAI,
            input_price=20,
            output_price=80,
            reasoning_effort="high",
            eligible=True,
            max_token="200k",
            expensive=True,
            force_system_message_to_inject=markdown_instruction_enhanced,
            link="https://platform.openai.com/docs/models/o3-pro",
            input_modality="TI",
            output_modality="T",
            effort_options=effort_options,
        ),
        ModelDeclaration(
            name="o3",
            company=LLMNames.OPENAI,
            input_price=2,
            output_price=8,
            reasoning_effort="high",
            eligible=True,
            max_token="200k",
            # is_vision_enabled=False,
            force_system_message_to_inject=markdown_instruction_enhanced,
            link="https://platform.openai.com/docs/models/o3",
            input_modality="TI",
            output_modality="T",
            effort_options=effort_options,
        ),
        ModelDeclaration(
            name="gpt-4o-mini-2024-07-18",
            company=LLMNames.OPENAI,
            # description="affordable and intelligent small model for fast, lightweight tasks.",
            input_price=0.15,
            output_price=0.6,
            max_token="128k",
            eligible=True,
            # is_vision_enabled=True,
            link="https://platform.openai.com/docs/models/gpt-4o-mini",
            input_modality="TI",
            output_modality="T",
        ),
        # ModelDeclaration(
        #     name="o3-mini",
        #     company=LLMNames.OPENAI,
        #     input_price=1.10,
        #     output_price=4.40,
        #     # reasoning_effort = 'high',
        #     eligible=True,
        #     max_token="200k",
        #     has_image_generation=True,
        #     is_vision_enabled=False,
        #     force_system_message_to_inject = markdown_instruction,
        #     link="https://platform.openai.com/docs/models/o3-mini",
        # ),
    ]
