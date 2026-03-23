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
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

logger = logging.getLogger(__name__)


# "A": "unknown"|"matched"|"probably_not_match"


reasoner_with_answer = """
This task involves **visual 3D modeling and analysis** using an auxiliary tool called the **“imagery module.”**
Your goal is to solve the problem through an *imagery-based reasoning process* (described below), interacting iteratively with this module.

The **imagery module** offers the capability to rotate objects and get the snapshot for the camera angle position.

The **interaction** proceeds in **turns**.
Each turn follows this pattern:

1. **Your turn**: Analyze the provided images and reasoning notes (stored “memory” from prior turns).
   Then, produce your output, consisting of (a) updated reasoning and (b) rotation commands for the imagery module.
2. **Imagery module’s turn**: The module executes your commands, generates new images, and supplies them as context for the next iteration.

The question asks you to rotate the original to match the alternative, but it is the same to rotate the alternative to match the original. In this task, the imagery module will provide rotation capability of the alternatives, so that you have to match the original.

The **imagery module is stateful** — it preserves each object’s camera position between iterations.

> ⚠️ **Important:**
>
> * Each call to you represents **one iteration (one turn)** in the ongoing process.
> * **Do not simulate multiple turns** or the imagery module’s responses.
> * In each turn, **produce output**, then stop after returning a JSON object.

---

### Command System

**Valid targets:**
`A`, `B`, `C`

**Operations:**
`left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`

**Operation details:**

* `left`: rotate object left by the specified degree.
* `right`: rotate object right by the specified degree.
* `up`: tilt object upward by the specified degree.
* `down`: tilt object downward by the specified degree.
* `rotate:cw`: rotate object clockwise by the specified degree.
* `rotate:ccw`: rotate object counterclockwise by the specified degree.

Note: Rotation directions in the command are defined relative to the object, not the camera. As a result, they are the inverse of camera rotations. For example, `right:15` rotates the object 15° to the right. This is equivalent to **moving** the camera 15° to the left, or `yaw:-15`.

**Command syntax:**
Each command consists of the operation and degree separated by a colon.
Examples:

* `"left:15"`
* `"rotate:cw:30"`

**Rotation sequence syntax:**
A rotation sequence is a comma-separated list of commands applied in order.
Examples:

* `"left:15,right:15,up:15"`
* `"right:10,right:10,right:10"`

---

### Output Format

For each iteration (turn), return output in the following JSON format:

```json
{
  "memory": {
    "current_iteration": integer (e.g., 1, 2, 3...),
    "current_focusing_alternative": "A",
    "feedback_image_analysis": "Analysis of the resulting rotate command images",
    "match_status_updated": {
        "A": "proven_match|proven_mismatch|investigating|waiting",
        "B": ...
        "C": ...
    },
    "next_to_focus_alternative": "A",
    "estimate_rotation_distance": "Put the best estimated distance to the target, in direction and degrees, to direct your next action",
  },
  "commands": [
    {
      "target": "A|B|C",
      "rotation_sequence": "right:15,right:15,up:10"
    }
  ],
  "final_answer": "A|B|C|null"
}
```

**Field explanations:**

* **`memory.current_iteration`**:
  Integer indicating which iteration/turn this output corresponds to (starting from `1` and increasing each turn).

* **`commands`**:

  * List of rotation directives for one or more targets.
  * Each `target` corresponds to a model that will generate a **composite image**: the sequence of rotations you specify will produce one snapshot per rotation step.
  * For example:

    * `"right:10,right:10,right:10"` generates 3 incremental views.
    * A `"right:0"` command produces an image from the current view (no rotation).

* **`final_answer`**:

  * Set the solution label (`"A"`, `"B"`, or `"C"`) if you have reached ~~to~~ a conclusion, or `null` otherwise.

**IMPORTANT** Always output as json object. Even for final answer.

---

### Think with Imagery

**IMPORTANT** — Use an *imagery-based reasoning approach* to solve this problem as described below. The main idea is that you reasoning process and conclusion should be heavily relied and grounded on concrete images, the snapshot images generated by the imagery module. You **SHOULD NOT** rely only on reasoning process. To say that the object are the same is to find the final rotation where they look exactly the same, this will be the visual evidence.

1. The object images provided in the problem statement (i.e, the camera view of the object) are such that:

   * If one can be rotated to obtain (visually match) another one **exactly** same view angle, then both objects are **identical** (so, is not the answer).
   * If no rotation can make them match no matter you repeat rotations, they are probably different, so is a solution candidate.

2. **Work sequentially through all alternatives** (A, then B, then C).

   * In each turn, focus on one alternative at a time.
   * based on the last generate image, guess the rotation distance and direction to the target, and generate the rotation command sequence on that direction.
   * get the snapshot result image, and check if it matches the original.
   * if yes, repeat another turn, to get a single snapshot image that matches the original. This will be the match evidence. Mark the alternative as 'matched'.
   * if not, repeat the process, repeat to guess the rotation direction and distance, and generate the sequence command.
   * If you have rotated in all directions possible, have stressed out, then mark as "probably_not_match".
   * To consider as stressed out, make sure to rotate in 360 degrees, in all directions, horizontal, vertical and the roll equivalent rotation 
   * Repeat at least 3 turns for that alternativebefore consider that don´t match.

3. Do in phases.

   * To gain an initial orientation, request a longer rotation sequence, even a full 360°rotation sequence.
   * Once familiar with the shape, proceed with **smaller, incremental rotations** to refine and locate the correct matching orientation.
   * Each rotation step will produce a **snapshot** image, which will help you visualize current progress and guide the next move. The next rotation will be a continuation. Consider the last snapshot to direct the next rotatio command.

4. **PROOF OF MATCH**
   * To alternatives that you come to conclusion that match, do an additional turn to generate a **PROOF OF MATCH** image. Request a no rotate command (left:0) and generate a single snapshot image that looks VERY SIMILAR to the original, that fullfill the condition that the image can be obtained by rotating the other.

5. Deep search required

   * If you went through all the alternatives once and came to an inconclusive result, for example, if all alternatives could match or if more than one appears to be a valid candidate, then repeat the process another turn of investigation.
   * If looks that all the alternatives are matched, something is missing. Pass again to all of them and look carefully to find the difference. If necessary, rotate to get a better view, until identify the odd one. To get the current position snapshot, request a no rotate command (left:0)
   * If there are more than one alternative that don't match, generate longer sequence of rotations on those ones and try to find if there is any that can match. All the alternatives unless one, match the original.
   * **DON'T GIVE UP**.

""".strip()

reasoner_with_answer_GEMINI = """
This task involves **visual 3D modeling and analysis** using an auxiliary tool called the **“imagery module.”**
Your goal is to solve the problem through an *imagery-based reasoning process* (described below), interacting iteratively with this module.

The **imagery module** offers the capability to rotate objects and get the snapshot for the camera angle position.

The **interaction** proceeds in **turns**.
Each turn follows this pattern:

1. **Your turn**: Analyze the provided images and reasoning notes (stored “memory” from prior turns).
   Then, produce your output, consisting of (a) updated reasoning and (b) rotation commands for the imagery module.
2. **Imagery module’s turn**: The module executes your commands, generates new images, and supplies them as context for the next iteration.

The question asks you to rotate the original to match the alternative, but it is the same to rotate the alternative to match the original. In this task, the imagery module will provide rotation capability of the alternatives, so that you have to match the original.

The **imagery module is stateful** — it preserves each object’s camera position between iterations.

> ⚠️ **Important:**
>
> * Each call to you represents **one iteration (one turn)** in the ongoing process.
> * **Do not simulate multiple turns** or the imagery module’s responses.
> * In each turn, **produce output**, then stop after returning a JSON object.

---

### Command System

**Valid targets:**
`A`, `B`, `C`

**Operations:**
`left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`

**Operation details:**

* `left`: rotate object left by the specified degree.
* `right`: rotate object right by the specified degree.
* `up`: tilt object upward by the specified degree.
* `down`: tilt object downward by the specified degree.
* `rotate:cw`: rotate object clockwise by the specified degree.
* `rotate:ccw`: rotate object counterclockwise by the specified degree.

Note: Rotation directions in the command are defined relative to the object, not the camera. As a result, they are the inverse of camera rotations. For example, `right:15` rotates the object 15° to the right. This is equivalent to **moving** the camera 15° to the left, or `yaw:-15`.

**Command syntax:**
Each command consists of the operation and degree separated by a colon.
Examples:

* `"left:15"`
* `"rotate:cw:30"`

**Rotation sequence syntax:**
A rotation sequence is a comma-separated list of commands applied in order.
Examples:

* `"left:15,right:15,up:15"`
* `"right:10,right:10,right:10"`

---

### Search Strategy & Logic (Think with Imagery)

You are an expert 3D analyst. Your goal is to prove whether the alternative (A, B, C) is the **same object** as the Original by finding a camera angle where they look **identical**.

**CRITICAL RULE: YOU MUST BE EXHAUSTIVE.**
LLMs tend to give up too early. You must not give up. You must not conclude "different" until you have viewed the object from all sides (Front, Back, Top, Bottom).

**Phase 1: Global Survey (The "Spin")**
*   If you have just started with an alternative, do not try to "guess" the match immediately. You likely have the wrong orientation.
*   **Action:** Send a command to rotate the object significantly to see multiple sides (e.g., `right:90, right:90, right:90`).
*   Gather visual data on the object's topology.

**Phase 2: Coarse Alignment**
*   Compare the "Survey" images with the Original. Look for specific landmarks (handles, holes, protrusions).
*   **Action:** Rotate the alternative to bring the matching landmark into roughly the same position.
*   **Correction Logic:**
    *   If the feature is too far to the left => command `right:X`.
    *   If the feature is too high => command `down:X`.
    *   **If the object looks "tilted" or "rotated" relative to the horizon** => You **MUST** use `rotate:cw` or `rotate:ccw` to align the roll. **Do not state "the angle is off" without issuing a command to fix it.**

**Phase 3: Fine Tuning & Verification**
*   Once roughly aligned, use small increments (`up:10`, `left:5`) to get a perfect lock.
*   **Proof of Match:** If you believe they are the same, you must generate a final **Proof Image** (a `left:0` command) where the two images are visually indistinguishable.

**Phase 4: Concluding**
*   **Matched:** Only mark as "matched" if you have generated the Proof Image.
*   **Not Matched:** Only mark as "not match" if you have completed Phase 1 (seen all sides) and Phase 2 (attempted alignment) and found irreconcilable geometric differences (e.g., "Original has a hole, Alternative does not").

---

### JSON Output Format

You must return a JSON object.
**IMPORTANT:** `final_answer` MUST remain `null` until you have completed the verification phase for all candidates.

```json
{
  "memory": {
    "iteration_count": integer,
    "current_target": "A|B|C",
    "search_phase": "Survey|Alignment|Verification|Finished",
    "visual_analysis": "Detailed comparison of landmarks. E.g., 'The handle is visible on the left in Original, but currently on the right in Alternative.'",
    "orientation_hypothesis": "E.g., 'I need to flip it 180 degrees horizontally and tilt it down 30 degrees.'",
    "status_log": {
       "A": "proven_match|proven_mismatch|investigating|waiting",
       "B": "...",
       "C": "..."
    }
  },
  "commands": [
    {
      "target": "A|B|C",
      "rotation_sequence": "string (e.g., 'right:90,right:90,right:90' or 'up:15,rotate:cw:10')"
    }
  ],
  "final_answer": "A|B|C|null"
}
```

### Constraints & Negative Constraints

1.  **NO EXCUSES:** Never say "the camera angle is slightly different" as a reason for mismatch. If the angle is different, **your job is to rotate the object to match that angle.**
2.  **STAY IN LOOP:** Do not output a `final_answer` in the first 3 turns of any specific alternative. You must gather data.
3.  **MANAGE TILT:** If the object matches but is "leaning," use `rotate:cw` or `rotate:ccw`.
4.  **EXHAUSTIVE:** If you cannot see the back of the object, you cannot conclude it doesn't match. You must rotate it.


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


class ToolsBackedImageryReasoner_Eval_07099:

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
        imagery = StatefulImageryHumanFriendRotationModule_7(
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
