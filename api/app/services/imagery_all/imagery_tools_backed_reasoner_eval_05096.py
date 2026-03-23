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

This is a visual 3D modeling problem.

To solve it, you will have to understand the spatial structure of the objects based on 2D projection images from different angles.

To help you with this, you will have access to a tool called the “imagery module”. More than that, in this task, it is required to resolve it in an "imagery way" (explained below).

The imagery module has structural knowledge of the object and can perform consistent camera manipulations that result in 2D snapshots from different angles of the object.

To interact with the imagery module, you generate, as output, predefined rotation commands (details below).

Working with the imagery module tool is an iterative process.

You alternate turns with the imagery module. In your turn, you do the necessary analysis steps and generate requests for the next rotation commands. Then, the imagery module applies the commands and generates the 2D snapshot images. These images are provided in the next turn as context in the conversation.

The imagery module is stateful throughout the entire iteration. This means that the camera position for each object is fixed between iterations.

Each call (each turn in the iteration process) is atomic and isolated. So, you will generate a “memory” with the current rationale annotation so that, in the next turn, you will have access to it and can continue reasoning and remember the partial conclusions. This makes it possible to create a unique and continuous reasoning chain toward resolving the problem.

The imagery module lacks intelligence (e.g., it cannot help infer the problem solution); its only capability is object rotation via predefined commands. Your role is to conduct the inference.

**IMPORTANT**: The iteration process itself is controlled externally. Each call to you represents **ONE TURN** in this process. Do NOT simulate the back-and-forth turns. Just execute one step in your role in each call. Output one JSON object and then STOP.

### Commands

You can generate commands for more than one target at once. For each target, generate a sequence of one or more commands.

Targets can be: `original`, `A`, `B`, or `C`.

Operations can be: `left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`.

* `left`: rotate the model to the left by the given degree.
* `right`: rotate the model to the right by the given degree.
* `up`: rotate the model up by the given degree.
* `down`: rotate the model down by the given degree.
* `rotate:cw`: rotate the model clockwise by the given degree.
* `rotate:ccw`: rotate the model counter-clockwise by the given degree.

A command is the operation followed by the degree. Example: `"left:15"`, `"right:15"`, `"up:15"`, `"down:15"`, `"rotate:cw:15"`, `"rotate:ccw:15"`.
A rotation sequence is a comma-separated string of commands. Example: `"left:15,right:15,up:15"`, `"right:15,right:15,right:15"`.

### Output

Generate the output in JSON using the following format:

```json
{
  "memory": {
    "current_iteration": integer (e.g., 1, 2, 3...),
    "rationale": "Short description of your rationale and partial conclusion for later reference",
    "suspicion_ranking": "List ordered by likelihood of being the odd one (e.g., ['B', 'A', 'C']), your partial conclusion",
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
  "final_answer": "your final answer to the problem or null if you are in the investigation process"
}
```

More details:

* `current_iteration`: set to `1` for the first turn and increment by one thereafter.
* `commands`:

  - Generate commands for one or more targets.
  - Each target (each entry in the `commands` list) will generate one image file.
  - For each target, generate one command or a sequence of rotations. Each rotation will generate a thumbnail-like image in the composite image file.
  - For one target, prefer executing a sequence in a single entry instead of using multiple entries.
* `final_answer`: leave as `null` during investigation/analysis. At the end of the investigation, set the alternative of the problem. This problem has one and only one alternative (A, B, or C). Setting the alternative will finish the problem resolution.

---

### **Think with Imagery**

- **IMPORTANT** Your task is to think (conduct the investigation) in an imagery way.
- In an imagery way, think and proceed always **grounded** in images.
- For each partial or final conclusion, generate the best possible image state to support that conclusion, like double-checking through clear image generation.
- Do it in an iterative way. So, for example, instead of saying, "this is different, and that is the same, because this or that", the expected way is to say, "I think this alternative is this way; let me try to generate an angled view to support that fact".
- And, the images will allow you to say "with that image, we can see clearly that this is different from that", or like "but let me check the other side" or "another angle", or "let me try to see the other side or a full rotation, a 360-degree view". This is just an example of what it means to be "grounded in images". It is like using images to "prove" your assumptions.
- Work in a focused way. If you suspect that the odd one is alternative A, then you should put A side by side with the original, thus "focusing" on this alternative.
- Work in an incremental way. Generating too much rotation or working with all the alternatives at once can disturb the focus. Visual focus is a detailed process; focusing too broadly will cause you to lose attention.
- Repeat the iteration as long as necessary, because looking at each part can take time, and it is OK; it is part of the imagery way of thinking.
- Double-check as much as possible. If you come to suspect an alternative, make multiple comparisons until you have high confidence, again backed by clear image generation.
- **IMPORTANT** When you have the final candidate, do at least one more iteration, comparing this candidate only with the original side by side, to have clear evidence of the difference. Then, only after that, give the final answer.
- **IMPORTANT** Repeat at least 5 iterations in total before giving the final answer. You can repeat more, but do not answer before 5 iterations.



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


class ToolsBackedImageryReasoner_Eval_05096:

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

                    # no final answer, valid rotation sequence. Valid output!
                    valid = True
                    break

                if not valid:
                    raise Exception(
                        f"Invalid or no rotation_sequence found. {response}"
                    )

                # -- continues iteration --
                # build history for reasoning
                rationales.append({"role": "assistant", "content": response})

                command_images = []
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

                        content = f"[image generated by Imagery Module {imagery.__class__.__name__}] for target {target} and rotation sequence {command.get('rotation_sequence')}"
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
