"""
memo:
- Manter um histórico da iteraracão entre o imagery e reasoning, e passar os últimos N (uns 4), porque é como a gente pensa. A gente
lembra as últimas iterações.

"""

import asyncio
import json
from pathlib import Path

from app.llm_services.any_model import AnyModel
from app.models.chat_message import ModelWithParameters
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json
from app.utils.prompt_loader import get_prompt

MAX_ITERATION = 3

REASONING_MODEL = "chatgpt-4o-latest"
IMAGERY_MODEL = "gemini-2.0-flash-preview-image-generation"


class ImageryReasoner:

    @staticmethod
    async def reason_loop(
        chat_history, model: str | ModelWithParameters, options=None, save_raw=True
    ):

        model_name = REASONING_MODEL

        async def call_llm(history, model_name, options):
            print(
                "\n------------------------->>>\ncall_llm:>>>",
                json.dumps(history, indent=2, cls=CustomJSONEncoder),
            )
            _answer, _image_url, _files, _meta = await AnyModel().chat(
                history, model_name, options
            )
            if save_raw:
                chat_history.append(
                    dict(
                        role="assistant",
                        content=_answer,
                        image_url=_image_url,
                        files=_files,
                        meta=_meta,
                        persist=True,
                    )
                )
            print(
                "\n-------------------------<<<\ncall_llm:<<<",
                json.dumps(
                    _meta if isinstance(_meta, dict) else _meta.model_dump(),
                    indent=2,
                    cls=CustomJSONEncoder,
                ),
            )
            return _answer, _image_url, _files, _meta

        reasoner_system_message = get_prompt(
            Path(__file__).resolve().parent, "prompt-for-reasoning-module.txt"
        )
        imagery_system_message = get_prompt(
            Path(__file__).resolve().parent, "prompt-for-imagery-module.txt"
        )

        history = chat_history[:]  # history holds the history for this interation only

        rationale_history = []  # only <rationale> entries
        last_imagery_request_response = []  # imagery last generated image entry
        imagery_instruction_and_result = (
            []
        )  # <ask to imagery> + resulting image sequence

        iter_count = 0
        iter_steps = []
        while iter_count < MAX_ITERATION:
            iter_count += 1

            # call reasoner module with imagery module aware prompt, and last image if exists
            print(
                f"\n=================== Call reasoning model {iter_count} ==================\n"
            )
            response, _, _, _ = await call_llm(
                [{"role": "system", "content": reasoner_system_message}]
                + history
                + rationale_history
                + last_imagery_request_response,
                model_name,
                options,
            )

            # if models decide to finish, return
            response_dict = parser_json(response)
            if "final_answer" in response_dict:
                return response_dict["final_answer"], chat_history, iter_steps

            # if there is no instruction to imagery, finish
            if not "instructions_to_imagery" in response_dict:
                return response, chat_history, iter_steps

            # -- continues iteration --
            # build history for reasoning

            if "rationale" in response_dict:
                rationale_history.append(
                    {
                        "role": "assistant",
                        "content": f"rationale: {response_dict['rationale']}",
                    }
                )

            # history for imagery
            imagery_instruction = response_dict["instructions_to_imagery"]
            imagery_instruction_and_result.append(
                {
                    "role": "assistant",
                    "content": f"instructions_to_imagery: {imagery_instruction}",
                }
            )

            MAX_RETRY = 5
            attempts = 0
            while True:
                attempts += 1
                print(
                    f"\n=================== Call imagery model {iter_count} attempt: {attempts}/{MAX_RETRY}==================\n"
                )
                try:
                    response, image_url, files, meta = await call_llm(
                        [
                            {  # system message
                                "role": "system",
                                "content": imagery_system_message,
                            }
                        ]
                        + history  # conversation history, with original image
                        + imagery_instruction_and_result[
                            -2:
                        ],  # previous instruction->previous generate image -> last instruction
                        IMAGERY_MODEL,
                        {
                            "use_image_generation": True,
                            "use_image_generation__options": {"quality": "low"},
                        },
                    )
                    if image_url:  # OK
                        break
                    else:
                        raise Exception(f"Image not generated {response}")
                except Exception as e:
                    print(f"Error: {e}")
                    if attempts <= MAX_RETRY:
                        print(
                            f"\n*** Image not generated in attempts {attempts}/{MAX_RETRY}! Sleep {2**attempts} seconds and retry"
                        )
                        await asyncio.sleep(2**attempts)
                    else:
                        raise  # give-up

            # imagery history
            last_imagery_request_response = [
                {
                    "role": "assistant",
                    "content": f"instructions_to_imagery: {imagery_instruction}",
                },
                {"role": "assistant", "image_url": image_url},
            ]

            # imagery history
            imagery_instruction_and_result.append(
                {"role": "assistant", "image_url": image_url}
            )

        # exceed iterations, call without system message
        print(f"\n=================== Call reasoning model PLAIN ==================\n")
        answer, _, _, _ = await call_llm(
            history + rationale_history + last_imagery_request_response,
            model_name,
            options,
        )

        return answer, chat_history, iter_steps
