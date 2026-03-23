import asyncio
import datetime
import json

import logging
from pathlib import Path
import traceback

from openai import BaseModel
from app.llm_services.any_model import AnyModel
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.models.file_category import FileCategory
from app.services.imagery_all.stateful_imagery import StatefulImageryModule
from app.services.imagery_all.stateful_imagery_4_no_shadow_perspective import (
    StatefulImageryModule4NoShadowPerspective,
)
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

logger = logging.getLogger(__name__)

# memo:
# this is a ablation study prompt.
# removed the part the 5 iteration and the evidence coaching part.
# make the prompt more neutral

prompt_for_reasoner = """

You are given a visual problem to solve.

To solve the problem, you may need a deeper understanding of the object, such as a spatial (3D) understanding or a different viewing angle.

To help with this, you will work along with a module called the imagery module.

The imagery module has structural knowledge of the object in the problem. It can manipulate the object consistently and generate views from different angles.

To interact with the imagery module, you generate image manipulation (understood as camera movement) commands as output. The imagery module will receive these commands, execute them, and generate the resulting snapshot images. In the next iteration, these images will be passed to you, and you will continue the reasoning.

So, this is an iterative process. It is a back-and-forth process between you and the imagery module.

IMPORTANT: Produce exactly ONE iteration per response. Do NOT simulate multiple back-and-forth steps in a single response. Output exactly one JSON object and then stop.

# More about the imagery module

The imagery module is stateful; it will retain the object (or camera angle) state between iterations.

The imagery module is passive: it only performs an action in response to a command you provide.

The imagery module has no intelligence (it does not infer the solution to the problem). Its only capability is manipulating the object using predefined commands.

All reasoning and the final solution are entirely your responsibility. The imagery module only assists by providing alternative views and serves as an anchor for your reasoning process.

At each iteration, in your turn, generate the following output:

* current_iteration: the current iteration number. The iteration number is sequential and starts with 1.
* rationale: brief working summary (1-3 sentences). No step-by-step reasoning.
* next_step: what you need to investigate next
* commands: the commands, for you next step.
* final_answer: your final answer, if you have reached an answer and want to finish. Otherwise, set it as null.

If `final_answer` is null, include at least one imagery command.
If `final_answer` is not null, `commands` must be an empty list.
Hard limit: maximum 8 iterations; at the limit, answer with best effort.

All past rationales will be passed to you as context. However, for images returned by the imagery module, only the last 3 images will be provided in the context (image memory is shorter).

# Commands

You may generate commands for more than one target, and for each target you may provide a sequence of one or more commands.

Targets can be: original, A, B, or C.

Commands are provided as a comma-separated string. Each command is an operation plus a value.

Operations can be: yaw, pitch, roll, or reset.

Values:

* For yaw, pitch, roll: an angle in degrees (can be negative or positive).
* For reset: x, y, z, or iso.

Camera and axes:

* World Z-axis points upward.
* The camera moves around the object's center (focal point).
* Yaw is a rotation around the global Z-axis (think longitude around the object).
* Pitch tilts the camera up/down relative to its current view.
* Roll spins the camera around its own forward axis (like rotating the screen).

Operations:

* reset:x/y/z/iso: instantly move to a standard view. x and y are side views at the horizon, z is top-down, iso is an isometric corner view.
* yaw: orbit around global Z. Works best after reset:x/y/iso. From reset:z it will tip the camera off the top view.
* pitch: orbit vertically (latitude). Positive goes over the top; negative goes underneath.
* roll: spin the screen without changing camera position, especially useful for top-view cardinal rotation.

Movement pattern examples:
A) Horizontal orbit: reset:y, yaw:30, yaw:30, yaw:30 (walk around the object).
B) Vertical rotation: reset:y, pitch:45, pitch:45 (look over/under).
C) Top-down spin: reset:z, roll:90, roll:90 (keep top view while rotating north/east/south/west).
D) Isometric inspection: reset:iso, yaw:15, pitch:-10 (standard 3D perspective with depth).

# Output

Generate output in JSON using the following structure (no code block formatting):

```
{
  "thought_process": {
    "current_iteration": integer,
    "rationale": "brief working summary (1-3 sentences)",
    "next_step": "your next step plan"
  },
  "commands": [
    {
      "target": "original|A|B|C",
      "rotation_sequence": "reset:iso,yaw:90,pitch:-20,yaw:90"
    },
    {
      "target": "original|A|B|C",
      "rotation_sequence": "reset:iso,yaw:90,pitch:-20,yaw:90"
    }, (continues)
  ],
  "final_answer": null or your answer to the visual problem
}
```

Return valid JSON only. No extra keys. No trailing commentary.
`commands` must be `[]` or a non-empty list; never omit it.



""".strip()

reasoner_for_final_answer = """
For this visual problem, generate the answer in the following json format:
```json
{
  "force_stop": true,
  "final_answer": "Your answer to the visual problem",
}
```
"""

logger = logging.getLogger(__name__)


class ResponseWithoutAnswer(BaseModel):
    rationale: str
    rotation_sequence: str


class TargetAndCommand(BaseModel):
    target: str
    rotation_sequence: str


class ResponseForReasoner(BaseModel):
    thought_process: dict
    final_answer: str | None
    commands: list[TargetAndCommand] | None


def rationale_with_imagery_response(rationales, imagery_images):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
        # for image, include only the last 3 images
        if i >= len(imagery_images) - 3:
            for image_url in imagery_images[i]:
                rationale_with_imagery_resonse.append(
                    dict(role="assistant", image_url=image_url)
                )
    return rationale_with_imagery_resonse


def invalid(cmd_string):
    # Valid command format: "yaw:10,pitch:30,roll:-10"
    allowed_commands = {"yaw", "pitch", "roll", "reset"}
    if not isinstance(cmd_string, str):
        return True
    cmds = [cmd.strip() for cmd in cmd_string.split(",") if cmd.strip()]
    if not cmds:
        return True
    for cmd in cmds:
        if ":" not in cmd:
            return True
        command, value = cmd.split(":", 1)
        if command.strip().lower() not in allowed_commands:
            return True
        if command != "reset":
            try:
                float(value)
            except Exception:
                traceback.print_exc()
                return True
        else:
            if value not in ["x", "y", "z", "iso"]:
                return True
    return False


class ToolsBackedImageryReasoner_Eval91:

    # REASONING_MODEL = 'chatgpt-4o-latest'
    # REASONING_MODEL = 'gpt-5.1-chat-latest'
    # REASONING_MODEL = 'gpt-5.2-chat-latest'
    REASONING_MODEL = "gpt-5.2"
    # REASONING_MODEL = 'gemini-3-pro-preview'

    @classmethod
    async def reason_loop(
        cls,
        chat_message: ChatMessage,
        model: str | ModelWithParameters,
        options=None,
        save_raw=True,
    ):

        model_name = cls.REASONING_MODEL

        async def call_llm(history, model_name, options):
            print(
                f"\n------------------------->>>\ncall_llm {model_name}:>>>",
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
                        created_at=get_now(),
                        persist=True,
                    )
                )
            _meta = _meta if isinstance(_meta, dict) else _meta.model_dump()
            output = _meta.get("output") or _answer
            print(
                f"\n-------------------------<<<\ncall_llm {model_name}:<<<",
                json.dumps(output, indent=2, cls=CustomJSONEncoder),
            )
            return _answer, _image_url, _files, _meta

        def get_now():
            nonlocal datetime_incrementer
            datetime_incrementer += 1000
            return (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.datetime.resolution * datetime_incrementer
            )

        # --- main body ---
        datetime_incrementer = 0
        bounds_map = chat_message.imagery_args["bounds_map"]
        # foundation_image_url = chat_message.imagery_args['foundation_image_url']

        # create the stateful imagery model
        imagery = StatefulImageryModule4NoShadowPerspective(
            bounds_map, off_screen=True, show_grid=False
        )
        try:

            # question image and question
            chat_history = [
                dict(
                    role="user",
                    file_url=chat_message.imagery_args["question_image_url"],
                    file_name=chat_message.imagery_args["question_file_name"],
                    content_type="image/png",
                    created_at=get_now(),
                    id=None,
                    persist=True,
                ),
                dict(
                    role="user",
                    content=chat_message.message,
                    created_at=get_now(),
                    id=None,
                    persist=True,
                ),
            ]

            freeze_history = chat_history[
                :
            ]  # history holds the history for this interation only

            MAX_ITERATION = 20
            iter_count = 1

            rationales = []
            imagery_images = []
            while iter_count <= MAX_ITERATION:

                # call reasoner module with imagery module aware prompt, and last image if exists
                logger.info(
                    f"\n=================== Call REASONING model {iter_count} ==================\n"
                )

                # if iter_count <= MIN_ITERATION:
                #     reasoner_system_message = reasoner_with_answer
                #     response_schema = ResponseWithoutAnswer.model_json_schema()
                # else:
                reasoner_system_message = prompt_for_reasoner
                response_schema = ResponseForReasoner.model_json_schema()

                reasoning_retry_cout = 5
                valid = False
                while reasoning_retry_cout > 0:
                    reasoning_retry_cout -= 1
                    response, _, _, _ = await call_llm(
                        [{"role": "system", "content": reasoner_system_message}]
                        + freeze_history
                        + rationale_with_imagery_response(rationales, imagery_images),
                        model_name,
                        options={
                            "response_mime_type": "application/json",
                            "response_json_schema": response_schema,
                        },
                    )

                    response_dict = parser_json(response)
                    if not isinstance(response_dict, dict):
                        logger.info(f"Not a dictionary. RETRY {reasoning_retry_cout}")
                        continue

                    final_answer = response_dict.get("final_answer")
                    if final_answer:
                        logger.info('"final_answer" found. Finish')
                        return final_answer, chat_history, None

                    # if there is no instruction to imagery, finish
                    commands = response_dict.get("commands")
                    if not commands:
                        logger.info(f"No commands found. RETRY {reasoning_retry_cout}")
                        continue

                    # for command in commands:
                    #     rotation_target = command.get('target')
                    #     rotation_sequence = command.get('rotation_sequence')
                    #     if not rotation_target or not rotation_sequence or invalid(rotation_sequence):
                    # rotation_sequence, rotation_target = response_dict.get('rotation_sequence'), response_dict.get('rotation_target')
                    # if not rotation_sequence or invalid(rotation_sequence):
                    #     print( f'Invalid or no rotation_sequence found. RETRY {reasoning_retry_cout}')
                    #     continue

                    # no final answer, valid rotatino sequence. Valid output!
                    valid = True
                    break

                if not valid:
                    raise Exception(
                        f"Invalid or no rotation_sequence found. {response}"
                    )

                # print(f"rotation_target: {rotation_target}, rotation sequence:{rotation_sequence}")

                # -- continues iteration --
                # build history for reasoning
                rationales.append({"role": "assistant", "content": response})

                command_imaages = []
                for command in commands:
                    # call imagery
                    target = command.get("target")
                    if target.lower() == "original":  # fix 'Original' to 'original'
                        target = "original"
                    logger.info(
                        f"\n==[{cls.__name__}]================= Call IMAGERY {command.get('target')} {command.get('rotation_sequence')} ==================\n"
                    )
                    image_path = imagery.run_sequence_and_save_image(
                        target, command.get("rotation_sequence")
                    )
                    logger.info(f"==[{cls.__name__}] image_path: [{image_path}]: <<")
                    if image_path:  # OK

                        # read image bytes
                        with open(image_path, "rb") as f:
                            file_content = f.read()

                        # upload to S3
                        image_url = await S3UploadServices.upload_generate_image(
                            Path(image_path).name,
                            file_content,
                            Path(image_path).suffix.lstrip("."),
                            FileCategory.GENERATED,
                        )
                        logger.info(f"image_url: [{image_url}]: <<")
                        if not image_url:
                            raise Exception(f"Error uploading file to S3 {image_path}")
                        else:
                            # await wait for 10 seconds
                            await asyncio.sleep(10)

                        if save_raw:
                            chat_history.append(
                                dict(
                                    role="assistant",
                                    content=f"[image generated by {imagery.__class__.__name__}]",
                                    image_url=image_url,
                                    created_at=get_now(),
                                    persist=True,
                                )
                            )

                        command_imaages.append(image_url)

                    else:
                        raise Exception(f"Image not generated {response}")

                # imagery history
                imagery_images.append(command_imaages)

                iter_count += 1

            # exceed iterations, call without system message
            logger.info(
                f"\n=={cls.__name__}================= Exceeded MAX. Reasoning model LAST call ==================\n"
            )
            response, _, _, _ = await call_llm(
                [{"role": "system", "content": reasoner_for_final_answer}]
                + freeze_history
                + rationale_with_imagery_response(rationales, imagery_images),
                cls.REASONING_MODEL,
                options,
            )

            response_dict = parser_json(response)
            return response_dict.get("final_answer", response), chat_history, None

        finally:
            imagery.close()
