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
from app.services.imagery_all.stateful_imagery_5_human_friend_rotation import (
    StatefulImageryHumanFriendRotationModule_5,
)
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

logger = logging.getLogger(__name__)


reasoner_with_answer = """
### Problem Description

The problem involves a static 2D image.

To solve it, you eventually need to understand the spatial structure of the objects, because 2D images can hide parts of the structure. Also, different viewing angles can result in different 2D images, even if they depict the same object.

To help you with this, you will have access to a tool called the **“imagery module.”** Moreover, it is **required** that you think in an **imagery** way. This is the main objective of this exercise.

The imagery module **has** structural knowledge of the object and can perform consistent camera manipulations that result in 2D snapshots from different angles.

To interact with the imagery module, you generate predefined manipulation commands (details below).

This is an iterative process. In each iteration, you request a camera movement and receive the resulting angled image.

You alternate turns with the imagery module. In your turn, you do the necessary analysis and finish by requesting new angles. Then, the imagery module makes the rotations and generates the images. These images are provided to you in the next turn as context in your conversation.

The imagery module is stateful. This means the camera position for each object is fixed between iterations.

Each call to you (each turn in the iteration process) is atomic and isolated. So, you will be requested to generate a “memory” with the current rationale annotation so that, in the next turn, you will have access to it and can continue your reasoning. This makes it possible to create a unique and continuous reasoning chain toward resolving the problem.

The imagery module lacks intelligence (e.g., it cannot infer the problem solution); its only capability is object manipulation via predefined commands. Your role is to conduct the inference; the role of the imagery module is to support you with camera movements.

**IMPORTANT**: The iteration process itself is controlled externally. Each call to you represents **ONE TURN** in this process. Do NOT simulate multiple back-and-forth steps. Just execute one step in each call. Output exactly one JSON object and then STOP.

### Commands

You can generate commands for more than one target. For each target, generate a sequence of one or more commands.

Targets can be: `original`, `A`, `B`, or `C`.
Commands: Provided as a string separated by commas. Each command consists of an operation and a value.

Operations can be: `left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`.

* `left`: rotate the model to the left by the given degree.
* `right`: rotate the model to the right by the given degree.
* `up`: rotate the model up by the given degree.
* `down`: rotate the model down by the given degree.
* `rotate:cw`: rotate the model clockwise by the given degree.
* `rotate:ccw`: rotate the model counter-clockwise by the given degree.

A command is the operation followed by the degree. Example: `"left:15"`, `"right:15"`, `"up:15"`, `"down:15"`, `"rotate:cw:15"`, `"rotate:ccw:15"`.
A rotation sequence is a comma-separated string of commands. Example: `"left:15,right:15,up:15"`.

### Output

Generate the output in JSON using the following format:

```json
{
  "memory": {
    "current_iteration": integer (e.g., 1, 2, 3...),
    "rationale": "Short description of your rationale and partial conclusion",
    "plan": "Your next step plan"
  },
  "commands": [
    {
      "target": "original|A|B|C",
      "rotation_sequence": "rotation sequence for this target"
    },
    {
      "target": "original|A|B|C",
      "rotation_sequence": "rotation sequence for this target"
    }
  ],
  "final_answer": "your answer to the visual problem or null if you are not sure yet."
}
```

More details:

* `current_iteration`: set to `1` for the first turn and increment by one thereafter.
* `commands`:

  * Generate commands for one or more targets.
  * Generate commands aligned with your current plan.
  * Each target (each entry in the `commands` list) will generate a unique image (composite image).
  * For each target, generate one command or a sequence of camera movements. Each movement will be represented by a thumbnail-like image in a composite image.
  * For one target, prefer executing a sequence in a single entry instead of using multiple entries.
* `rotation_sequence`:

  * Generate as one string, with commands separated by `,`, and operation and value separated by `:`. Example: `"right:15,right:15,right:15"`
* `final_answer`: Leave this field as `null` during your investigation. Set a value only when you have concluded your investigation and are sure of your answer. This will end the iteration process.

---

### **Think with Imagery**

**IMPORTANT** Think in an imagery way, not purely in a reasoning way. This means:

* Think **grounded in images**.
* Conduct the process in an incremental investigative way. In each step, generate clear evidence images. Work in a focused way. Don't generate too much or too broadly. Don't generate too many images in one iteration.
* Prefer a longer investigative session instead of an overly compressed, high-density reasoning chain of thought.
* To understand the inner structure, it helps to generate a longer sequence of camera movement commands.
* Create incremental rotation sequences with small changes (for example, a sequence in the same direction of 15 degrees).
* If the objects are the same, then there will always be a rotation sequence in which they look exactly the same. If they are not, then there will exist an angle such that, no matter what rotations you do, they will never look the same.
* The perspective given in the problem already shows a perspective that can be used to validate it, which means that, no matter how you rotate the other, you will not have that view. So, the wrong one will be more difficult to reach from the original (or vice versa—from the wrong alternative to the original) than the correct (matching) ones.
* Use reasoning to conduct the investigation and narrow down the candidates, but rely heavily on clear image evidence to make partial conclusions and the final answer.
* play aroud with each of the images, to get the understanding of the inner structure, for a few iteration. Double check, based on generated image evidence, of this understanding.
* when you have the final candidate, do at least one more iteration, comparing this candidate only with the original, to have clear evidence of the difference. Then, only after that, give the final answer.
* repeat the iterations as many times as necessary until get clear evidence. Alternate between broad and deep investigation. For deep investigation, it is better to restrict the a candiate alternative comparing with the original. Also helps, for deep investigation, request for a long sequece of commands, to have a clear view of the entire object structure. The imagery module can accept from 1 to as long as a sequence to cover entire 360 degree (ex: `right:30,left:30,..`, a sequence of 12 times). 
* The examplos of command sequences are only **examples**. You don't need to follow these examples. If you understand how to use the commands, use in full power to help anchor your reasoning. Variability in which command use, the degree, the sequence length, the number of iterations, the targets. Use all the possibilities to conduct your investigation and help you get the more precise and correct answer as possible.
* **IMPORTANT**: The most expected behavior is you work and try to generate a rotation to match the alternative with the original, and fix that rotation. Remember that the imagery module is stateful. Where you leave the object, is where it will stay. So, remember the last position, see how close the positions are and play with it. It is like **fit** and object in a box, where you need to find the right rotation to fit the object in the box.More than infere and get the answer, it is about the correct image evidence. This is key part of your task in this exercise.
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
        if i >= len(imagery_images) - 3:
            for image_url in imagery_images[i]:
                rationale_with_imagery_resonse.append(
                    dict(role="assistant", image_url=image_url)
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


class ToolsBackedImageryReasoner_Eval_05094:

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
        imagery = StatefulImageryHumanFriendRotationModule_5(
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
            MIN_ITERATION = 5
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
                reasoner_system_message = reasoner_with_answer
                response_schema = ResponseWithAnswer.model_json_schema()

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
                        print(f"Not a dictionary. RETRY {reasoning_retry_cout}")
                        continue

                    final_answer = response_dict.get("final_answer")
                    if final_answer:
                        print('"final_answer" found. Finish')
                        return final_answer, chat_history, None

                    # if there is no instruction to imagery, finish
                    commands = response_dict.get("commands")
                    if not commands:
                        print(f"No commands found. RETRY {reasoning_retry_cout}")
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
                    print(
                        f"\n==[{cls.__name__}]================= Call IMAGERY {command.get('target')} {command.get('rotation_sequence')} ==================\n"
                    )
                    image_path = imagery.run_human_sequence_and_save_image(
                        target, command.get("rotation_sequence")
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
