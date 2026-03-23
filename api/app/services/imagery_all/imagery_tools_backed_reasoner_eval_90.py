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


prompt_for_reasoner = """
# Problem Description
The problem involves a static 2D image. 

To solve it, you need a deeper understanding of the object, such as spatial (3D) awareness or different viewing angles.

To assist with this, you have access to a tool called the imagery module. 

This module possesses structural knowledge of the object and can perform consistent manipulations, returning the result as a static 2D image (simulating a camera view).

To interact with the imagery module, you must generate commands and you will receive the resulting 2D image. 

This is an iterative process. You may repeat it as many times as necessary.

The imagery module is stateful: the object status is the result of the last manipulation you requested. The module is passive and only executes actions in response to your specific commands.

The imagery module lacks intelligence (e.g., it cannot infer the problem solution); its only capability is object manipulation via pre-defined commands. The final solution and necessary reasoning are exclusively your responsibility. 

The imagery module serves only to provide different views and anchor your reasoning process.

# Interaction Guidelines
Execute at least 5 iterations. Initially, do not focus on the final result; instead, focus on analyzing and deepening your understanding of each alternative and the original object. 

From iteration 6 onwards, you may continue analysis or generate the final result.

In each iteration, generate the following information:
- iteration number: sequential number, starting with 1.
- rationale: your reasoning up to this point. This serves as your memory.
- next step plan: what to investigate in the next iteration.
- Commands: the command for the imagery module (details below).
- Final answer: after iteration 5, you may provide the final result.

All text output you generate will be passed back in the context for the next iteration. However, for the images returned by the imagery module, only the last 3 will be retained. Therefore, enrich the rationale field in your output to preserve context.

# Commands
You can generate commands for more than one target. For each target, generate a sequence of commands.

Targets can be: original, A, B, or C.
Commands: Provided as a string separated by commas. Each command consists of an operation and a value.

Operations can be: yaw, pitch, roll, or reset.
Values can be:
- For yaw, pitch, roll: the angle in degrees. Can be negative or positive.
- For reset: x, y, z, or iso.

Below is the explanation of coordinates and details for each operation:


Camera Logic & Coordinate System:
The Global Z-axis is "Up." The camera always faces the center of the object.
1. RESET: Teleports the camera to a starting position.
   - Use 'x' or 'y' for side views (horizon level).
   - Use 'z' for a top-down view (map view).
   - Use 'iso' for a diagonal corner view.
2. YAW (Degrees): Orbits the camera horizontally around the Global Z-axis.
   - Use this to walk around the object.
3. PITCH (Degrees): Orbits the camera vertically (up or down).
   - Positive values fly over the top; negative values fly under.
4. ROLL (Degrees): Spins the camera view clockwise/counter-clockwise.
   - This rotates the screen without moving the camera's position.

Critical Rules for Movement:
- When in a side view (Reset X, Y, or Iso), use 'yaw' to orbit horizontally.
- When in a top-down view (Reset Z), DO NOT use 'yaw', as this will swing the camera down toward the horizon. Instead, use 'roll' to rotate the map orientation while maintaining the top-down perspective.

Examples:
- "Walk around the object": reset:y, yaw:30, yaw:30
- "Look over the top from the front": reset:y, pitch:45, pitch:45
- "Top-down map view, rotated 90 degrees": reset:z, roll:90
- "Isometric view with a slight depth adjustment": reset:iso, yaw:15, pitch:-10


# Output
Generate the output in JSON using the following format:

{
  "thought_process": {
    "iteration_number": integer (e.g., 1, 2, 3...)
    "rationale": Your reasoning so far. This is your memory.
    "next_step_plan": Detailed reasoning for the next commands...
  },
  "commands": [
    {
      "target": original|A|B|C, 
      "rotation_sequence": rotation commands for this target.
    },
    {
      "target": original|A|B|C, 
      "rotation_sequence": rotation commands for this target.
    }, ...
  ],
  "final_answer": your answer to the visual problem or null if you are not sure yet.
}

# Hints
- Do exhaustive analysis, don't rush to answer.
- Answer backed by clear envidence picture generation, which mean, generate evidences to support your answer.
- You can rotate not only the original but the alternatives as well.
- You can apply the same rotation command to more than one target in one iteration. It helps comparisona end evidence generation.

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


class ToolsBackedImageryReasoner_Eval90:

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
