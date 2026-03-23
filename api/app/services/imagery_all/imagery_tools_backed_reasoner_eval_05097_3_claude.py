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
### Task: Visual Matching Through Rotation

You have access to an **imagery module** that can rotate 3D objects and generate snapshot images. Your task is to determine which option (A, B, or C) CANNOT be obtained by rotating the original cube stack.

### Core Method: Rotate and Match

**The ONLY reliable way to solve this problem is through visual matching:**

1. **Rotate each option (A, B, C) systematically** to try matching it with the original
2. **If you find a rotation where an option looks EXACTLY like the original** → that option CAN be obtained by rotation (not the answer)
3. **If after thorough rotation attempts, an option never matches the original** → that option CANNOT be obtained by rotation (this is the answer)

**Critical Rule:** You MUST rely on visual evidence from rotation snapshots. Do NOT attempt to solve through structural analysis or inference alone.

### Interaction Process

- You work in **turns** with the imagery module
- Each turn: You request rotations → Module provides snapshots → You analyze and continue
- The module maintains object positions between turns (stateful)
- Each call represents ONE turn only - output JSON then STOP

### Commands

**Targets:** `original`, `A`, `B`, `C`

**Operations:** 
- `left:degrees` - rotate left
- `right:degrees` - rotate right  
- `up:degrees` - rotate up
- `down:degrees` - rotate down
- `rotate:cw:degrees` - rotate clockwise
- `rotate:ccw:degrees` - rotate counter-clockwise

**Examples:**
- Single: `"right:30"`
- Sequence: `"right:30,up:15,rotate:cw:45"`
- Current view: `"left:0"` (generates snapshot without rotation)

### Required Approach

**For EACH alternative (A, B, C):**

1. **Initial Exploration (Turn 1-2):**
   - Generate a rotation sequence to understand the object's structure
   - Try major rotations (90°, 180°) to see different faces
   - Compare visually with the original

2. **Matching Attempts (Turn 3-5):**
   - Based on initial observation, rotate to positions that might match
   - Use incremental rotations (15-30°) to fine-tune
   - Always compare the rotated position with the STATIC original

3. **Verification (Turn 6+):**
   - If a match is found: Generate side-by-side evidence (`"left:0"` for both)
   - If no match after thorough attempts: Mark as candidate answer
   - Double-check with additional angles if needed

**Important Guidelines:**

- **DO NOT** rotate both objects and compare - always compare rotated alternative against static original
- **DO NOT** conclude based on structural reasoning - require visual evidence
- **DO** explore systematically - try all major axes and combinations
- **DO** spend at least 2 turns per alternative before moving to the next
- **DO** generate clear visual evidence before marking anything as "matched" or "unmatched"

### Output Format

```json
{
  "iteration": 1,
  "current_focus": "A|B|C|verification",
  "observation": "What you see in the current snapshots",
  "matching_status": {
    "A": "untested|testing|matched|no_match",
    "B": "untested|testing|matched|no_match", 
    "C": "untested|testing|matched|no_match"
  },
  "next_action": "What you plan to do next",
  "commands": [
    {
      "target": "original|A|B|C",
      "rotation_sequence": "rotation commands"
    }
  ],
  "final_answer": null
}
```

**Field Descriptions:**

- `iteration`: Current turn number (1, 2, 3...)
- `current_focus`: Which alternative you're currently testing
- `observation`: Describe what you see in the snapshots
- `matching_status`: Track progress for each alternative
  - `untested`: Not yet examined
  - `testing`: Currently rotating and comparing
  - `matched`: Found rotation that matches original
  - `no_match`: Exhaustively tested, cannot match
- `next_action`: Your plan for the next rotation
- `commands`: Rotation requests for this turn
- `final_answer`: Set to "A", "B", or "C" only when certain (otherwise null)

### Critical Reminders

1. **Visual matching is the ONLY conclusive evidence** - textual analysis is unreliable
2. **Rotate systematically** - don't jump to conclusions after one or two rotations
3. **Focus on one alternative at a time** - complete testing before moving on
4. **Generate evidence images** - when you think you found a match, create side-by-side comparison
5. **The answer exists** - exactly ONE option cannot be rotated to match the original

### Starting Strategy

Begin with alternative A:
1. First, try 90° rotations on each axis to see major faces
2. Look for distinctive features that match/don't match the original
3. Fine-tune promising positions with smaller rotations
4. If matched, move to B; if exhaustively unmatched after several turns, it's likely the answer but still check B and C

Remember: You're looking for the ONE option that CANNOT match the original through any rotation.

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


class ToolsBackedImageryReasoner_Eval_05097_3:

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
