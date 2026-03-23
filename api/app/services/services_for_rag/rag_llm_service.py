import asyncio
import datetime
import json
import traceback

import openai

from app.language_models.llm_factory import LLMFactory
from app.services.services_for_rag.prompt_loader import get_prompt

MODEL_FOR_FAST_TASK = "gemini-2.5-flash-lite"
MODEL_FOR_FAST_VISION_TASK = "gemini-2.5-flash-lite"


def parser_json(answer: str) -> dict:
    answer = answer.replace("```json", "").replace("```", "").strip()
    try:
        obj = json.loads(answer, strict=False)
    except Exception as e:
        print(f"Error parsing json string: type(e)={type(e)}. Error occurred: {e}")
        traceback.print_exc()
        obj = answer

    return obj


def get_current_date_hour():
    from zoneinfo import ZoneInfo

    try:
        brasilia_tz = ZoneInfo("America/Sao_Paulo")
        now = datetime.datetime.now(brasilia_tz)
        return f"{now}"
    except Exception as e:
        print("Error getting Sao Paulo timezone. Fallback to GMT-3", e)
        offset = datetime.timezone(datetime.timedelta(hours=-3))
        now = datetime.datetime.now(offset)
        return f"{now}"


class RagLLMService:

    @staticmethod
    async def _call_llm_with_retry(messages, model, options=None):
        MAX_RETRIES = 3
        MAX_RETRIES_FOR_BACKOFF = 12
        attempt = 0
        while True:
            attempt += 1
            try:
                answer, image_url, files, meta = await LLMFactory.create_by(
                    model
                ).achat(messages=messages, model=model, options=options)
                return answer, image_url, files, meta  # success

            except Exception as e:
                print(f"\n*** Error **** {e}")
                status_code = getattr(
                    getattr(e, "response", None), "status_code", None
                ) or getattr(e, "code", None)
                if status_code == 400:  # fatal error
                    raise
                elif status_code == 503:
                    if (
                        attempt <= MAX_RETRIES_FOR_BACKOFF
                    ):  # server overloaded. retry with backoff
                        t = 2 ** min(attempt, 6)  # max wait of 128s
                        print(
                            f"\n*** retrying after backoff of {t} seconds.  ({attempt}/{MAX_RETRIES_FOR_BACKOFF})…"
                        )
                        await asyncio.sleep(t)
                        continue
                    else:
                        raise
                elif attempt <= MAX_RETRIES:
                    print(f"\n*** retrying ({attempt}/{MAX_RETRIES})…")
                    await asyncio.sleep(3)
                    continue
                else:
                    raise

        # won't happen
        return None, None, None, None

    @staticmethod
    async def generate_image_caption(image_url):
        system_message = "Given an image, generate a 1-paragraph text that describes what is in that image, for later reference."
        messages = [
            dict(role="system", content=system_message),
            dict(
                role="user",
                content=[
                    dict(type="image_url", image_url=dict(url=image_url)),
                ],
            ),
        ]
        model = MODEL_FOR_FAST_VISION_TASK
        answer, _, _, meta = await RagLLMService._call_llm_with_retry(messages, model)
        return answer, meta  # success

    @staticmethod
    async def generate_one_paragraph_introduction(content):
        system_message = (
            "Given a text provided by the user, generate a one line introduction describing what is the "
            "text about and what the text contains, for the purpose of later content search."
        )
        messages = [
            dict(role="system", content=system_message),
            dict(role="user", content=content),
        ]

        answer, _, _, meta = await RagLLMService._call_llm_with_retry(
            messages, MODEL_FOR_FAST_TASK
        )
        return answer, meta

    @staticmethod
    async def generate_introduction_for_file(
        file_url: str, file_name: str, content_type: str
    ):
        system_message = (
            "Given the file provided by the user, generate a one paragraph introduction describing what the file "
            "talk about what what it covers, in all its extend. The purpose of this introduction if to decide if a content is covered by this file or not, and in what extent."
        )

        messages = [
            dict(role="system", content=system_message),
            dict(
                role="user",
                content=[
                    dict(
                        type="file_url",
                        file_url=dict(
                            url=file_url,
                            content_type=content_type,
                            file_name=file_name,
                        ),
                    ),
                ],
            ),
        ]
        answer, _, _, meta = await RagLLMService._call_llm_with_retry(
            messages, MODEL_FOR_FAST_TASK
        )
        return answer, meta

    @staticmethod
    async def review_prompt_for_semantic_search_and_keywords(chat_history, prompt):
        SIMILARITY_WINDOW_SIZE = 4

        # use oly the last N messages, without system message
        plain_messages = [
            f"{m.get('role')}: {m.get('content')}"
            for m in chat_history[-SIMILARITY_WINDOW_SIZE:]
            if m.get("role") != "system"
        ]
        # if len(plain_messages)<= 0:
        #     answer = message
        # else:
        plain_messages = "\n".join(plain_messages)
        messages = [
            dict(role="system", content=get_prompt("prompt_enhancer.txt")),
            dict(
                role="user",
                content=f"--- CURRENT DATE TIME ---\n{get_current_date_hour()} (São Paulo/Brasil)",
            ),
            dict(
                role="user",
                content=f"--- CHAT HISTORY ---\n{plain_messages}\n--- USER'S QUESTION ---\n{prompt}",
            ),
        ]

        answer, _, _, meta = await RagLLMService._call_llm_with_retry(
            messages, MODEL_FOR_FAST_TASK
        )

        answer_as_dict = parser_json(answer)
        if not isinstance(answer_as_dict, dict):
            print("Could not get json answer. fallback to original prompt")
            # fallback to original
            return answer, [], meta

        print(
            f"\n\n********* ORIGINAL question: {prompt}, REVISED question and keywords: {answer_as_dict}\n"
        )
        return (
            answer_as_dict.get("prompt", prompt),
            answer_as_dict.get("keywords", []),
            meta,
        )

    @staticmethod
    async def ask_for_relevant_files(prompt_with_context, files):

        file_list_text = "\n----\n".join(
            f"file_no: {index+1}\nfile_name: {f.get('file_name')}\nintroduction:\n{f.get('introduction')} "
            for index, f in enumerate(files)
        )

        messages = [
            dict(role="system", content=get_prompt("pickup-deep-relevant-files.txt")),
            dict(
                role="user",
                content="---START OF LIST OF FILES---\n"
                + file_list_text
                + "\n---END OF LIST OF FILES---\n",
            ),
            dict(role="user", content="QUESTION: " + prompt_with_context),
        ]

        print("ask_for_relevant_files >>>: messages:", messages)

        answer, _, _, meta = await RagLLMService._call_llm_with_retry(
            messages, MODEL_FOR_FAST_TASK
        )

        print("ask_for_relevant_files <<<: answer:", answer)
        answer_as_dict = parser_json(answer)
        if not isinstance(answer_as_dict, dict):
            print("Could not get json answer. fallback to original prompt")
            # fallback to original
            return []

        files_no = [
            d.get("file_no") - 1 for d in answer_as_dict.get("included_files", [])
        ]
        return files_no
