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
### Problem Description

This task involves **visual 3D modeling and analysis** using an auxiliary tool called the **“imagery module.”**  
Your goal is to solve the problem through an *imagery-based reasoning process* (described below), interacting iteratively with this module.

The **imagery module** performs controlled camera manipulations of 3D objects (rotations) and then generates 2D snapshot images from specific angles.  
Your role is to direct these rotations, analyze the resulting images, develop hypotheses, and decide the next rotation steps.

The interaction proceeds in **turns**.  
Each turn follows this pattern:

1. **Your turn**: Analyze the provided images and reasoning notes (stored “memory” from prior turns).  
   Then, produce your output, consisting of (a) updated reasoning and (b) rotation commands for the imagery module.
2. **Imagery module’s turn**: The module executes your commands, generates new images, and supplies them as context for the next iteration.

The **imagery module is stateful** — it preserves each object’s camera orientation between iterations.  
However, each call to you is **atomic and self-contained**: you must include your current iteration’s rationale and a short summary (“memory”) to maintain continuity across separate calls.

The imagery module itself is **not intelligent** — it cannot reason or analyze results.  
Your reasoning provides the intelligence, while the module only performs rotations according to your commands.

> ⚠️ **Important:**  
> - Each call to you represents **one iteration (one turn)** in the ongoing process.  
> - **Do not simulate multiple turns** or the imagery module’s responses.  
> - **Produce output for one turn only**, then stop after returning a JSON object.

---

### Command System

**Valid targets:**  
`original`, `A`, `B`, `C`

**Operations:**  
`left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`

**Operation details:**
- `left`: rotate object left by the specified degree.  
- `right`: rotate object right by the specified degree.  
- `up`: tilt object upward by the specified degree.  
- `down`: tilt object downward by the specified degree.  
- `rotate:cw`: rotate object clockwise by the specified degree.  
- `rotate:ccw`: rotate object counterclockwise by the specified degree.

Note: Rotation directions in the command are defined relative to the object, not the camera. As a result, they are the inverse of camera rotations. For example, `right:15` rotates the object 15° to the right. This produces the same visual result as rotating the camera 15° to the left, which is expressed as `yaw:-15`.

**Command syntax:**  
Each command consists of the operation and degree separated by a colon.  
Examples:
- `"left:15"`
- `"rotate:cw:30"`

**Rotation sequence syntax:**  
A rotation sequence is a comma-separated list of commands applied in order.  
Examples:
- `"left:15,right:15,up:15"`
- `"right:10,right:10,right:10"`

---

### Output Format

For each iteration (turn), return output in the following JSON format:

```json
{
  "memory": {
    "current_iteration": integer (e.g., 1, 2, 3...),
    "alignment_status": {
        "A": "unmatched" or "potential_match" or "confirmed_identical",
        "B": "unmatched",
        "C": "unmatched"
    },
    "focus_candidate": "A",
    "visual_observation": "Brief note on what the current rotation revealed (e.g., 'Side view of A matches the front view of Original').",
    "estimate_rotation_distance": "Put the best estimated distance to the target, in direction and degrees, do direct you next action",
    "plan": "Next rotation strategy."
  },
  "commands": [
    {
      "target": "original|A|B|C",
      "rotation_sequence": "right:15,right:15,up:10"
    },
    {
      "target": "original|A|B|C",
      "rotation_sequence": "left:10"
    }
  ],
  "final_answer": "A|B|C|null"
}
```

**Field explanations:**

- **`memory.current_iteration`**:  
  Integer indicating which iteration/turn this output corresponds to (starting from `1` and increasing each turn).

- **`memory.plan`**:  
  Brief explanation of your next analytical or observational plan, e.g., which rotations will help confirm or refine your hypothesis.

- **`commands`**:  
  - List of rotation directives for one or more targets.  
  - Each `target` corresponds to a model that will generate a **composite image**: the sequence of rotations you specify will produce one snapshot per rotation step.  
  - For example:  
    - `"right:10,right:10,right:10"` generates 3 incremental views.  
    - A `"right:0"` command produces an image from the current view (no rotation).

- **`final_answer`**:  
  - Set to the identified solution label (`"A"`, `"B"`, or `"C"`) **only when your investigation is complete**.  
  - Keep this field as `null` in ongoing turns while still gathering evidence or rotating views.

**IMPORTANT** Always output as json object. Even for final answer, output as json and put your answer in the `final_answer` field.

---

### Think with Imagery

**IMPORTANT** — Use an *imagery-based reasoning approach* to solve this problem as described below. The main idea is that you reasoning process and conclusiion should be heavily relied and grounded on concrete images. Here, the images are the snapshots generated by the imagery module. 

---

#### **Core Assumptions**

1. The object images provided in the problem statement (and in the initial state) are such that:
   - If one can be rotated to obtain (visually match) another one **exactly**, then both objects are **identical** (meaning that this pair is **not** the correct answer).
   - If no rotation can make them match, they are **different**, and that option is the **solution candidate**.
   - It means also that, if rotate both in some ways, and find a camera angle that they look exactly the same, it is not conclusive at all. For example, you can have a block with 3 cubes and other with 4 cubes stack and you can find an angle where both are seeing as 1 cube only. But, if you rotate the alternative and match the `original` in the initial position (zero rotation), or vice versa, than, this guarantee that they are the same. It means, one of them need to be unrotated from the beginning.
   - Based on that, the strategy to follow is to rotate one side until find a match with the other side.
   - In this problem, let fixed the `original` and rotate the alternatives, the visually match the `original`. **DON'T** rotate the `original`. Use the no rotation (left:0) command to request the initial state of the `original`, whenever necessary. For example, for comparison side by side.

---

#### **Imagery-Based Procedure**

1. **Work sequentially through all alternatives** (A, then B, then C).
   - In each turn, focus on one alternative at a time, unless for second pass when you passed all the alternatives and need to revisit again.
   - So, in for first pass, generate rotation command only to current `focus_candidate`, and eventually for `original` start state for comparison side by side. 

2. For each alternative:
   - Try to find a sequenc of rotation to visually match the original unrotated. 
   - If a match is found, the objects are identical — mark it as **potential_match**. 
   - If no match can be found despite all possible rotations, mark it as a **unmatched**.

3. For any alternative found to be identical to the original:
   - Repeat an additional turn to generate an **evidence image**, that is a single cut (**zero rotation** position, e.g. "left:0") of both, the alternative and the target, so that can be compared side by side, where it is expected to looks very similar, and them mark as **confirmed_identical**. This is the **clear evidence**, that gives **visual feedback**, the essence of what will call **magery way**.  

---

#### **Rotation and Observation Process**

- Finding the correct matching rotation is **iterative** and may require a process of **trial and error**:
  - Perform one of a sequence of rotation.
  - Analyze the last position from the genreate image, and have a grasp of the current camera state. Compare with the target and guess which are the directions to make it match to the target.
  - Decide on the next rotation direction and angle based on this evaluation.

- To gain an initial orientation, you may observe a **full 360°rotation sequence**.
- Once familiar with the shape, proceed with **smaller, incremental rotations** to refine and locate the correct matching orientation.
- Each rotation step will produce a **snapshot** image, which will help you visualize current progress and guide the next move.

---

#### **Iteration Strategy and Validation**

- For **each** alternative:
  - Conduct **at least two full analysis passes (turns)** before finalizing any conclusion.
  - State whether you’re performing a **broad scan** (exploratory rotation) or a **drill-down** (fine adjustment phase).
  - For **broader scan** helps ask for a longer sequence of rotations, and for **drill-down** helps ask for a smaller focused sequence of rotations.

- Perform **redundant and double-checking steps** to validate your conclusion:
  - Compare from multiple angles to ensure reliability.
  - Generate extra evidence or alternate view snapshots as necessary for confirmation.
  - Execute at least 6 iterations before giving the final answer. Think in **imagery way** always require additional steps for visual validation. Correct inference is not enough, generate visual evidence is always necessary.
  - Answer only after pass though all the alternatives, even you have strong evidence for one of them, you need to pass though all the alternatives to be sure.

#### **DEEP SEARCH REQUIRED**
  - If you went through all the alternatives once and came to an inconclusive result—for example, if all alternatives could match or if more than one appears to be a valid candidate—repeat the process another turn of investigation. 
  - If all the alternatives are mached, generate again the snapshots with no rotation (left:0) for all the alternatives along with the original, and do a one more static compasison, and select the most probable one. 
  - If there are more than one alternative that don't match, generate longer sequence of rotations on those ones and try to find if there is any that can match. 
  - **DON'T** give up in the first pass if the result is not conclusive. Repeat the process as many times as necessary.


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


def rationale_with_imagery_response_last_3_only(rationales, imagery_images):
    """
    This version pass throuth only the last 3 iterarations
    """
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_images
    ), "Rationale and imagery response must be in the same length"

    rationales = rationales[-3:]
    imagery_images = imagery_images[-3:]

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
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


class ToolsBackedImageryReasoner_Eval_05098:

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
                        + rationale_with_imagery_response_last_3_only(
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
                + rationale_with_imagery_response_last_3_only(
                    rationales, imagery_images
                ),
                cls.REASONING_MODEL,
                options,
            )

            response_dict = parser_json(response)
            return response_dict.get("final_answer", response), chat_history, None

        finally:
            imagery.close()
