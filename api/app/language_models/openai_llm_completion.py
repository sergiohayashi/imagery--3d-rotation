# from __future__ import annotations
#
# import json
# import time
# import traceback
# from typing import List, Union
#
# from openai import NOT_GIVEN
# from openai.types.chat import ChatCompletion
#
# from .LLMBase import LLMBase
# from .LLMModelDeclaration import LLMModelDeclaration
# from .openai_commons import get_async_client
# from .types.LLMNames import LLMNames
# from .types.models import ModelDeclaration
# from .types.opboos_chat_completion import OpBoostChatCompletion, OpBoostChatMessage
# from ..services.pricing import calculate_estimate_price
# from ..services.usage_log_service import UsageLogService
#
# default_model = 'mistral-large-latest'
#
#
# def parse_json_response(response: ChatCompletion):
#     json_response = response.choices[0].message.content
#     json_response = json_response.replace('```json', '').replace('```', '').strip()
#     try:
#         parse_json = json.loads(json_response, strict=False)
#     except Exception as e:
#         print(f"Error parsing json string: type(e)={type(e)}. Error occurred: {e}")
#         traceback.print_exc()
#         parse_json = response.choices[0].message.content
#
#     return parse_json
#
# markdown_instruction = "Formatting re-enabled"
# markdown_instruction_4o_latest = "Please format your response using proper markup and code formatting where applicable. For example, use Markdown for headings, lists, and inline code, and format code blocks with appropriate syntax highlighting. Ensure that all code snippets are enclosed in triple backticks (```) with the correct language specified for clarity"
#
# class OpenAILLM_Completion(LLMBase):
#
#     async def achat(self,
#                     messages: Union[list[OpBoostChatMessage], list[dict]],
#                     model: str = default_model,
#                     options: dict= None
#                     ) -> (dict | str, OpBoostChatCompletion):
#         start_t = time.time()
#
#
#         print('OpenAILLM.achat: message[-1]:>>>', messages[-1])
#         # print('OpenAILLM.achat: message:>>>', messages)
#         model_spec = LLMModelDeclaration.get_model(model)
#         # if model_spec.force_temperature:
#         #     temperature = model_spec.force_temperature
#
#         print( f'{model} reasoning_effort: {model_spec.reasoning_effort if model_spec.reasoning_effort else NOT_GIVEN}')
#
#         if model_spec.force_system_message_to_inject:
#             print( "Force inject system message: ", model_spec.force_system_message_to_inject)
#             messages = [{
#                 "role": "system",
#                 "content": model_spec.force_system_message_to_inject,
#             }] + messages
#
#         messages_to_send = []
#         for m in messages:
#             if isinstance(m['content'], str):
#                 if m.get('content'):
#                     messages_to_send.append({
#                         "role": m.get('role'),
#                         "content": m.get('content')
#                     })
#             else:
#                 _contents = []
#                 for p in m['content']:
#                     if p['type'] == "text":
#                         if not p.get('text') or p.get( 'text')== '(empty)':
#                             continue
#                         _contents.append({
#                             "type": "text",
#                             "text": p.get("text")
#                         })
#                     elif p['type'] == "image_url":
#                         if model_spec.is_vision_enabled:
#                             _file = p.get('image_url')
#                             _contents.append(p)   # format is already correct
#                     elif p['type'] == "file_url":
#                         _file = p.get('file_url')
#                         if 'image' in _file.get("content_type") and model_spec.is_vision_enabled:
#                             _contents.extend([{
#                                 "type": "text",
#                                 "text": f'filename: {_file.get("file_name")}'
#                             },{
#                                 "type": "image_url",
#                                 "image_url": {
#                                     "url": _file.get('url')
#                                 }
#                             }])
#                         else:
#                             continue
#
#                 messages_to_send.append({
#                     "role": m.get('role'),
#                     "content": _contents
#                 })
#
#         response = await get_async_client().chat.completions.create(
#             model=model,
#             messages=messages_to_send,
#             # temperature=config.default_temperature if temperature is None else temperature,
#             reasoning_effort = model_spec.reasoning_effort if model_spec.reasoning_effort else NOT_GIVEN,
#         )
#         print('OpenAILLM.achat: response:<<<', response)
#         # UsageLogService.register_usage(response)
#         answer = response.choices[0].message.content
#         meta = response.model_dump()
#         meta['estimate_price'], meta['input_tokens'], meta['output_tokens'] = calculate_estimate_price(model, meta['usage'])
#         meta['elapsed_in_sec'] = time.time() - start_t
#         # meta.estimate_price = calculate_estimate_price(model, meta.usage)
#         meta['company'] = LLMNames.OPENAI.name
#         UsageLogService.register_usage_meta(meta, LLMNames.OPENAI)
#         return answer, None, None, meta
#
#
#     # async def generate_image(self,
#     #                          prompt: str,
#     #                          model: str
#     #                          ) -> (str, dict):
#     #
#     #     raise Exception( "Not implemented")
#
#
#     models: List[ModelDeclaration] = [
#         ModelDeclaration(
#             name="gpt-4o-search-preview-2025-03-11",
#             company=LLMNames.OPENAI,
#             input_price=2.50,
#             output_price=10.0,
#             eligible=True,
#             max_token="128k",
#             is_vision_enabled=False,
#             has_web_search=True,
#             link="https://platform.openai.com/docs/models/gpt-4o-search-preview",
#             # accept_temperature=False,
#         ),
#         ModelDeclaration(
#             name="gpt-4o-mini-search-preview-2025-03-11",
#             company=LLMNames.OPENAI,
#             input_price=0.15,
#             output_price=0.6,
#             eligible=True,
#             max_token="128k",
#             has_web_search=True,
#             link="https://platform.openai.com/docs/models/gpt-4o-mini-search-preview",
#             # accept_temperature=False,
#         ),
#     ]
#
#
