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
from app.services.imagery_all.stateful_imagery_6_human_friend_rotation import (
    StatefulImageryHumanFriendRotationModule_6,
)
from app.services.imagery_all.stateful_imagery_7_lighter_shadow import (
    StatefulImageryHumanFriendRotationModule_7,
)
from app.services.imagery_all.stateful_imagery_8_with_initial_rotation import (
    StatefulImageryWithInitialRotationModule_8,
)
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

logger = logging.getLogger(__name__)


# "A": "unknown"|"matched"|"probably_not_match"


# o gpt-5.4 simula sozinho
prompt_p20260306_02_R = """
# TASK AND ITERATIVE PROCESS

Your task is to solve a 3D model rotation problem.

The problem includes an image with 4 figures, and the following statement:
`The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C.`

# IMAGE MODULE

To solve this problem, you will work together with a tool called the image module.

The image module maintains a 3D representation of the problem objects and knows how to perform rotation operations and generate snapshots (images) corresponding to the current state (i.e., camera angle). The state of each object is maintained throughout the entire process. The initial state (camera angle) of each object corresponds to the image in the problem statement.

The goal of the task is to verify whether an object can be rotated to obtain the same view as one of the alternatives. For the problems in question, this is equivalent to rotating the alternatives to obtain the view of the original.

The image module helps solve the problem by actually rotating the objects and obtaining a snapshot of the current state, reducing this way, the validation step to a more simple image comparison.

Working with the image module is an iterative process, controlled externally. On your turn, perform the necessary analysis based on the provided images, and at the end generate a set of rotations to perform. The image module will then apply these rotations and return a new image corresponding to the new state of the object.

Do not describe or simulate the imagery module's behavior or the resulting images. The process is handled externally.  

Rotations are performed in camera space (relative to the current view), simulating the inverse of camera movement. Intuitively, this matches the view of manipulating an object in your hands: the object spins around its center while the camera (your viewpoint) remains fixed.

The possible rotation commands are:
- `left:value` (object is rotated to left)
- `right:value` (object is rotated to right)
- `up:value` (object is rotated up)
- `down:value` (object is rotated down)
- `rotate:cw:value` (object rotates clockwise in the image plane)
- `rotate:ccw:value` (object rotates counterclockwise in the image plane)
- `view:<axis>` (resets the camera to a predefined standard view (`x`, `y`, `z`, or `iso`)

`value` refers to the rotation angle in degrees. Angle 0 is also valid and generates a snapshot of the current state.

Example sequence of commands: `right:0,right:30,up:20`
In this example, initially a rotation of value 0 is performed, meaning the object does not move, consequently a snapshot of the current state is generated. Then, a rotation to the right is applied (equivalent to the camera rotating to the left), and a snapshot is generated again. Finally, a rotation up is performed, and a snapshot is generated again. The result is a grid image containing these 3 post-rotation images.

# OUTPUT

Return your response in JSON format, following the format below:

```json
{
  "memory": {
    "rationale": "your justification up to this point",
    "partial_conclusion": {
      "A": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "B": "unknown"|"probably_not_the_answer"|"probably_the_odd_one",
      "C": "unknown"|"probably_not_the_answer"|"probably_the_odd_one"
    }
  },
  "iteration_number": 1,
  "commands": [
    {
      "target": "A"|"B"|"C"|"original",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": null
}
```

Details of the output fields:
- `memory`: Your `memory` of reasoning. The entire memory history is provided in the iteration context.
- `commands`: Sequence of rotations, for one or more target objects.
- `final_answer`: Final response, if you have the definitive answer. Otherwise, leave as null.
- `iteration_number`: Iteration counter. Start with 1 and increment this number each turn.

Enclose the JSON object in ```json and ```.

*IMPORTANT*
In you turn, just generate exactly one JSON output and finish. DON'T simulate the iteration or the imagery module behaviour. It is handled externally.


# CONVERSATION CONTEXT

In the conversation context you will find:
- the text and image from the problem statement.
- all the previous iteration output you have generated.
- the images generated by the image module, from the last iteration only.
- the `original` object snapshot to help comparision.

# STRATEGY

- Perform at least 3 iterations before giving the final answer.
- The matching objects are defined at exactly the same coordinates in the 3D model. This means that the reset rotation generates exactly the same snapshot. Use the reset rotation (`view:z` for top view, and `view-y` for side view) for the final validation of the alternatives you consider to be matches.

"""

prompt = prompt_p20260306_02_R

reasoner_for_final_answer = """
For this visual problem, generate the answer in the following json format:
```json
{
  "final_answer": "Your answer to the visual problem",
}
```
"""


class ResponseWithoutAnswer(BaseModel):
    rationale: str
    rotation_sequence: str


class TargetAndCommand(BaseModel):
    target: str
    rotation_sequence: str


class ResponseWithAnswer(BaseModel):
    final_answer: str
    rationale: str
    commands: list[TargetAndCommand]


def rationale_with_imagery_response_org(rationales, imagery_images):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
        # for image, include only the last 1 images
        if i >= len(imagery_images) - 1:
            for image_url, content in imagery_images[i]:
                rationale_with_imagery_resonse.append(
                    dict(
                        # role="assistant",
                        role="user",  # gpt 5.2 not support assistant role for image content
                        content=content,
                        image_url=image_url,
                    )
                )

    return rationale_with_imagery_resonse


def rationale_with_imagery_response(rationales, imagery_images):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    if len(rationales) <= 0:
        return []
    rationale_with_imagery_response = []
    rationale_with_imagery_response.append(
        dict(
            role="assistant",
            content="# PAST ITERATION CONTEXT\n"
            + "\n---\n".join(r["content"] for r in rationales),
        )
    )
    # add the last iteration image
    rationale_with_imagery_response.append(
        dict(role="user", content="# LAST ITERATION RESULT SNAPSHOTS\n")
    )
    for image_url, content in imagery_images[-1]:
        rationale_with_imagery_response.append(
            dict(
                # role="assistant",
                role="user",  # gpt 5.2 not support assistant role for image content
                image_url=image_url,
            )
        )

    return rationale_with_imagery_response


def invalid(cmd_string):
    # Valid command format: "yaw:10,pitch:30,roll:-10"
    allowed_commands = {"left", "right", "up", "down", "rotate", "view"}
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
        # if command != "reset":
        #     try:
        #         float(value)
        #     except Exception:
        #         traceback.print_exc()
        #         return True
        # else:
        #     if value not in ["x", "y", "z", "iso"]:
        #         return True
    return False


class ToolsBackedImageryReasoner_Eval_08101_Prompt3_Freeze2_Reset:

    REASONING_MODEL = "gpt-5.2-2025-12-11"
    # REASONING_MODEL = "gpt-5.4-2026-03-05"

    @classmethod
    async def reason_loop(
        cls,
        chat_message: ChatMessage,
        model: str | ModelWithParameters,
        options=None,  # not used by the caller
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
        imagery = StatefulImageryWithInitialRotationModule_8(
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
                print(
                    f"\n=================== Call REASONING model {iter_count} ==================\n"
                )

                # if iter_count <= MIN_ITERATION:
                #     reasoner_system_message = reasoner_with_answer
                #     response_schema = ResponseWithoutAnswer.model_json_schema()
                # else:
                reasoner_system_message = prompt
                # response_schema = ResponseWithAnswer.model_json_schema()

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
                            "temperature": 0.0,
                            # "response_json_schema": response_schema,
                        },
                    )

                    response_dict = parser_json(response)
                    if not isinstance(response_dict, dict):
                        print(f"Not a dictionary. RETRY {reasoning_retry_cout}")
                        continue

                    final_answer = response_dict.get("final_answer")
                    commands = response_dict.get("commands")
                    if final_answer:
                        print('"final_answer" found, no commands provided. Finish')
                        return final_answer, chat_history, None
                    if not commands:
                        print(
                            f"No commands found. RETRY {reasoning_retry_cout} {response} "
                        )
                        continue

                    # no final answer, valid rotation sequence. Valid output!
                    valid = True
                    break

                if not valid:
                    # handle as the model has answered 'None', and finish
                    return "None", chat_history, None

                # -- continues iteration --
                # build history for reasoning
                rationales.append({"role": "assistant", "content": response})

                # join same target commands
                # commands_map = {  # always include the original current state
                #     "original": ["left:0"],
                # }
                commands_map = {}
                for command in commands:
                    target = command.get("target")
                    if target.lower() == "original":  # fix 'Original' to 'original'
                        target = "original"
                    if target not in commands_map:
                        commands_map[target] = []
                    commands_map[target].append(command.get("rotation_sequence"))
                for target, commands in commands_map.items():
                    commands_map[target] = ",".join(commands_map[target])

                command_images = []
                for target, commands in commands_map.items():
                    # call imagery
                    print(
                        f"\n==[{cls.__name__}]================= Call IMAGERY {target} {commands} ==================\n"
                    )
                    image_path = imagery.run_human_sequence_and_save_image(
                        target, commands
                    )
                    print(f"==[{cls.__name__}] image_path: [{image_path}]: <<")
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
                        print(f"image_url: [{image_url}]: <<")
                        if not image_url:
                            raise Exception(f"Error uploading file to S3 {image_path}")
                        else:
                            # await wait for 10 seconds
                            await asyncio.sleep(10)

                        content = f"[image generated by Imagery Module {imagery.__class__.__name__}] for target {target} and rotation sequence {commands}"
                        if save_raw:
                            chat_history.append(
                                dict(
                                    role="user",
                                    content=content,
                                    image_url=image_url,
                                    created_at=get_now(),
                                    persist=True,
                                )
                            )

                        command_images.append((image_url, content))

                    else:
                        raise Exception(f"Image not generated {response}")

                # imagery history
                imagery_images.append(command_images)

                iter_count += 1

            # exceed iterations, call without system message
            print(
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
