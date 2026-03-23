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


prompt = """
# TASK AND ITERATIVE PROCESS
Your task is to solve a 3D visual matching problem in conjunction with an auxiliary tool called the imagery module.

The imagery module maintains a stateful representation of the 3D objects in the problem. It can manipulate (rotate) an object and generate a snapshot from the most recent camera angle. 

This is an iterative process. The iteration is controlled externally. In you turn, make the necessary analysis, and finish you turn by generating the output as specified below.

In each turn, you can generate one sequence of rotation commands for one or more targets. Then, the imagery module (controlled externally) will apply the commands and return a snapshot image after each command.

Valid targets are "original", "A", "B", and "C".
Valid commands are: `left`, `right`, `up`, `down`, `rotate:cw`, and `rotate:ccw`.

Rotations are performed in camera space (relative to the current view), simulating the inverse of camera movement:

- `left:<angle>` - Rotates the object leftward (equivalent to moving camera right/yaw right)
- `right:<angle>` - Rotates the object rightward (equivalent to moving camera left/yaw left)
- `up:<angle>` - Rotates the object upward (equivalent to moving camera down/pitch down)
- `down:<angle>` - Rotates the object downward (equivalent to moving camera up/pitch up)
- `rotate:cw:<angle>` - Rotates the object clockwise around the view axis (equivalent to camera roll CCW)
- `rotate:ccw:<angle>` - Rotates the object counterclockwise around the view axis (equivalent to camera roll CW)

Commands are followed by an angle. For example, `left:30` rotates the target object by 30 degrees.
Valid sequence examples: `left:30,right:30,up:30`, `left:0,rotate:ccw:90,rotate:cw:90`.
Each command in the sequencewill generate a snapshot image relative to the angle after the command is applied.
Rotation with value (0) generate the current state snapshot image.
All of the objects have the initial camera angle exactly as given in the problem statement image.

# OUTPUT
At the end of each iteration (i.e., at the end of your turn), generate output in JSON format as follows:
```json
{
  "memory": "your rationale so far",
  "commands": [
    {
      "target": "original|A|B|C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": "A|B|C|null"
}
```

- `commands` is a list. Each element targets one object and may contain one or more commands, as in the example.
- `final_answer` is the final answer. Fill this field only when you have the final answer; this will terminate the iterative process. Otherwise, set it to `null`.

# CONTEXT
All previous outputs will be provided in the context.
Only the most recent command output image (one for each requested target) will be provided.

# RULES
- Run at least 3 iterations. Give the final answer only from the 3rd iteration, NOT before.


"""


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


def rationale_with_imagery_response(rationales, imagery_images):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
        # for image, include only the last 3 images
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


def rationale_with_imagery_response_last_3_only(rationales, imagery_images):
    """
    This version pass throuth only the last 3 iterarations
    """
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationales = rationales[-2:]
    imagery_images = imagery_images[-2:]

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
        # if i >= len(imagery_images) - 1:   #include only the last 1 iteration image
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


def invalid(cmd_string):
    # Valid command format: "yaw:10,pitch:30,roll:-10"
    allowed_commands = {"left", "right", "up", "down", "rotate"}
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


class ToolsBackedImageryReasoner_Eval_08103_p1:

    # REASONING_MODEL = 'chatgpt-4o-latest'
    # REASONING_MODEL = 'gpt-5.1-chat-latest'
    # REASONING_MODEL = 'gpt-5.2-chat-latest'
    REASONING_MODEL = "gpt-5.2"
    # REASONING_MODEL = 'gemini-3-flash-preview'

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
                            # "response_json_schema": response_schema,
                        },
                    )

                    response_dict = parser_json(response)
                    if not isinstance(response_dict, dict):
                        print(f"Not a dictionary. RETRY {reasoning_retry_cout}")
                        continue

                    final_answer = response_dict.get("final_answer")
                    commands = response_dict.get("commands")
                    if final_answer and not commands:
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
