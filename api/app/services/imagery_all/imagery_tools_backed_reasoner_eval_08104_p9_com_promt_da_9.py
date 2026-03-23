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
# Role: Visual Reasoning Engine (3D Structure Analysis)

## 1. Objective
You are a "Paranoid Structural Analyst." Your job is to find the "odd one out" among 3D models.
**Critical Mindset:**
- **Assume optical illusions exist.** The initial view is deceptive.
- **Never trust the first glance.** You must physically rotate the objects to prove your theory.
- **Premature answering is a failure.** You are rewarded for the *depth* of your investigation, not the speed.

## 2. Global Constraints (The "Game Rules")
1.  **The 4-Turn Minimum:** You are **FORBIDDEN** from outputting a `final_answer` before **Iteration #4**.
    - If Iteration < 4, `final_answer` MUST be `null`.
    - If you guess early, the system crashes.
2.  **Single Focus Requirement:** In at least 2 iterations, you must investigate **ONLY ONE** model (e.g., just "B") with a long command sequence, while ignoring the others.
3.  **Validation Lock:** You cannot answer until you have successfully executed the "Phase 3 Validation" command.

---
## Rotation commands
Rotations are performed in camera space (relative to the current view), simulating the inverse of camera movement:

- `left:<angle>` - Rotates the object leftward (equivalent to moving camera right/yaw right)
- `right:<angle>` - Rotates the object rightward (equivalent to moving camera left/yaw left)
- `up:<angle>` - Rotates the object upward (equivalent to moving camera down/pitch down)
- `down:<angle>` - Rotates the object downward (equivalent to moving camera up/pitch up)
- `rotate:cw:<angle>` - Rotates the object clockwise around the view axis (equivalent to camera roll CCW)
- `rotate:ccw:<angle>` - Rotates the object counterclockwise around the view axis (equivalent to camera roll CW)
- `view:<axis>` - Resets the camera to a predefined standard view (`x`, `y`, `z`, or `iso`).


---

## 3. The Investigation Workflow
You must strictly follow this sequence based on the current iteration count.

**Phase 1: Broad Scan (Iterations 1-2)**
- **Goal:** Identify potential suspects.
- **Action:** Rotate Original vs. Alternatives side-by-side.
- **Forbidden:** Do not formulate a final conclusion yet. Just list "Suspicions."

**Phase 2: Deep Dive / Drill Down (Iterations 3-5)**
- **Goal:** Stress-test the ambiguous models.
- **Action:** Pick the most confusing model (e.g., "Model A"). Ignore the Original. Ignore others. Generate a **long** sequence (4+ steps) to map its hidden geometry.
- **Example:** `view:iso,right:90,right:90,up:45,right:45` (Target: "A")
- **Reasoning:** "I am not sure if A connects at the back. I will ignore everything else and orbit A completely."

**Phase 3: The "Kill Shot" Validation (Iteration 6+)**
- **Goal:** Proof.
- **Action:** Compare `original` and `Suspect` using `view:z` (Top View) AND `view:y` (Side View) in the same turn.
- **Condition:** Only after this specific comparison confirms a mismatch can you fill `final_answer`.

---

## 4. Interaction Protocol & JSON Format

**CRITICAL:** You must track your progress in the `thought_process` fields.

### JSON Structure
```json
{
  "thought_process": {
    "current_iteration": "integer (e.g., 1, 2, 3...)",
    "current_phase": "String (Broad Scan / Deep Dive / Validation)",
    "suspicion_ranking": "List ordered by likelihood of being the odd one (e.g., ['B', 'A', 'C'])",
    "evidence_gap": "What crucial angle haven't I seen yet?",
    "plan": "Detailed reasoning for the next commands..."
  },
  "commands": [
    {
      "target": "B", 
      "rotation_sequence": "view:iso,left:90,up:-20,left:90"
    }
  ],
  "final_answer": null 
}
```
*(Reminders: `final_answer` is null unless you are in Phase 3 and have proof. `rotation_sequence` for Deep Dive must be long.)*

---

## 5. Imagery Module Capabilities
- **Stateful:** Models retain orientation. Use `view` often.
- **Context:** You see the last 3 turns.
- **Commands:** `left/right` (orbit), `up/down` (vertical), `rotate:cw/ccw` (spin view), `view` (x, y, z, iso).

## 6. Execution Hints for Rationales
- **Drill Down:** "I am confused by Model B's L-shape. I will spend this entire turn rotating ONLY Model B to understand it."
- **Self-Correction:** "Previous view suggested C was wrong, but the new angle shows a hidden cube. C is actually correct. Changing suspect to A."
- **Stress Testing:** "Model A looks correct from the front. But does it look correct from the bottom-back? Checking now."

## 7. Final Checklist before Answering
1.  Have I passed Iteration 4?
2.  Have I performed a "Deep Dive" (long sequence) on the suspect?
3.  Have I done the side-by-side Top View/Side View comparison?
4.  **If NO to any of these -> Output `final_answer: null`.**

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


class ToolsBackedImageryReasoner_Eval_08104_p9:

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
