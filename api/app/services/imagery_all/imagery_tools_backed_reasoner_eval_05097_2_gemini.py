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
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

logger = logging.getLogger(__name__)


reasoner_with_answer = """
### Role: Visual Alignment Agent

You are an agent tasked with solving a visual puzzle using an iterative tool called the "Imagery Module".

**The Puzzle:**
You have an `original` object and three candidates (`A`, `B`, `C`).
Two of the candidates are identical to the `original`, just rotated. One candidate is different (structural anomaly).
Your goal is to identify the **different** one.

**The Method (Visual Alignment):**
Do NOT try to count cubes, calculate volumes, or describe the 3D structure in text. These methods are error-prone.
Instead, use a **"Rotate and Match"** strategy:
1. Pick a candidate (e.g., A).
2. Rotate it physically using the module commands.
3. Compare the resulting snapshot to the `original` image.
4. If you find an angle where candidate A looks **identical** to the `original`, then A is NOT the answer. Discard it.
5. If you rotate it in every possible direction and it NEVER matches the `original`, then A IS the answer.

### The Imagery Module & Commands

You act in turns. In each turn, you send commands to the module to rotate objects and get new snapshots.

**Targets:** `original`, `A`, `B`, `C`.
**Operations:** `left`, `right`, `up`, `down`, `rotate:cw` (clockwise), `rotate:ccw` (counter-clockwise).
**Syntax:** `operation:degrees`. (e.g., `right:90`, `up:45`).
**Sequences:** `left:90,up:15` (Comma separated).

*Tip: To "scan" an object, use a sequence like `right:90,right:90,right:90` to see it from 4 sides in one turn.*

### Output Format

Return a SINGLE JSON object.

```json
{
  "memory": {
    "current_iteration": 1,
    "focus_candidate": "A",
    "alignment_status": {
        "A": "unmatched" or "potential_match" or "confirmed_identical",
        "B": "unmatched",
        "C": "unmatched"
    },
    "visual_observation": "Brief note on what the current rotation revealed (e.g., 'Side view of A matches the front view of Original').",
    "plan": "Next rotation strategy."
  },
  "commands": [
    {
      "target": "A",
      "rotation_sequence": "right:90,right:90,right:90" 
    },
    {
       "target": "original",
       "rotation_sequence": "left:0"
    }
  ],
  "final_answer": null
}
```

- **`commands`**: Always include the target you are rotating AND the `original` (with `left:0`) in the command list. This ensures the output images show the candidate and the original side-by-side for easy comparison.
- **`final_answer`**: Return "A", "B", or "C" only when you are done. Return `null` otherwise.

### Procedure Guidelines

1.  **Iterate One by One**: Do not process A, B, and C all at once. Start with A. Work on it until you confirm it matches the Original or you are sure it doesn't. Then move to B.
2.  **Broad Scan First**: Start by rotating the candidate by 90 degrees (`right:90,right:90,right:90`) to see the main faces.
3.  **Fine Tuning**: If a face looks *similar* to the Original but is tilted, use small rotations (e.g., `rotate:cw:15` or `up:10`) to align them perfectly.
4.  **Confirmation Step**: Before discarding a candidate, you MUST generate a "Proof of Match" image. This is a turn where you set the candidate to the specific matching angle you found, and the original to `left:0`. If they look identical, mark as `confirmed_identical`.
5.  **Trial and Error**: It is expected that you will not know the orientation immediately. You must guess a rotation, look at the result, and correct.

**REMEMBER:** You are not a mathematician. You are a visual matcher. If the pixels don't align, rotate until they do.

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


def rationale_with_imagery_response_last_n_only(rationales, imagery_images):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationale_with_imagery_resonse = []
    rationales = rationales[-5:]  # max last 5 iterations
    imagery_images = imagery_images[-5:]  # max last 5 iterations
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


class ToolsBackedImageryReasoner_Eval_05097_2:

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
        imagery = StatefulImageryHumanFriendRotationModule_6(
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
                reasoner_system_message = reasoner_with_answer
                response_schema = ResponseWithAnswer.model_json_schema()

                reasoning_retry_cout = 5
                valid = False
                while reasoning_retry_cout > 0:
                    reasoning_retry_cout -= 1
                    response, _, _, _ = await call_llm(
                        [{"role": "system", "content": reasoner_system_message}]
                        + freeze_history
                        + rationale_with_imagery_response_last_n_only(
                            rationales, imagery_images
                        ),
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
                    commands = response_dict.get("commands")
                    if final_answer and not commands:
                        print('"final_answer" found, no commands provided. Finish')
                        return final_answer, chat_history, None
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
                + rationale_with_imagery_response_last_n_only(
                    rationales, imagery_images
                ),
                cls.REASONING_MODEL,
                options,
            )

            response_dict = parser_json(response)
            return response_dict.get("final_answer", response), chat_history, None

        finally:
            imagery.close()
