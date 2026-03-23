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

reasoner_with_answer_OLD = """
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

Think in an imagery way.
Imagery way means:

- Make conclusions always grounded in images. Images here are the current camera-angle views of the object.
- For each assumption, try to generate an image (camera-angle view) that serves as evidence for the assumption.
- In the imagery way, you work in a focused way, which means trying to check each alternative one at a time instead of all at the same time. Say, “now I am focusing on alternative A…”, then you can discard it or mark it as a candidate and proceed to the others.
- Think in an imagery way means relying less on pure reasoning (for example, “I think it is this or that”) and more on a one-at-a-time, image-grounded conclusion-making process.
- In the imagery way of thinking, it is normal to go back and forth between the alternatives when you are not sure of the answer.
- **IMPORTANT** Repeat at least 5 iterations in total before giving the final answer. More than that is OK, is desirable, but DO NOT answer before 5 iterations.
- **IMPORTANT** The images in this problem are given such that, if you can rotate one to match the other, then they are guaranteed to be the same. If not, they are not the same. Use this property to resolve the problem.
- The imagery way of resolving here is to rotate one and try to match the other. For example, rotate alternative A to match the original, or vice versa. You can also rotate both and match at another angle, but in this case, even if the image is the same, it is not guaranteed that they are the same anymore.
- In this way of resolving by rotating to match the other, make incremental rotation movements to understand in which direction to rotate. Because they are not based on a pure global axis, you need to adjust the direction while making small rotations. It can involve multiple turns even for a single alternative; this is the way imagery thinking works. It is okay; it is desirable in this case.
- Discovering the correct direction to rotate is a “do-action-verify” loop process. Rotating in the direction that matches the original problem image (the target) is the expected way to answer this problem; this is the imagery way of resolving.
- **IMPORTANT** For each alternative, that is not the solution, which means, are the same as the original, try to rotate until match the `original` one as is given in the problem statement image. This will be the prove that the alternative is not the solution. In this case, you don't need to rotate the `original`. Rotate both the same time will make the problem more difficult, visually speaking.
- After leave the object in the correct rotation position, generate a single image of the object by passing a command with value 0. For example "left:0". And double check if the image is same as the image of the `original` in the problem statement image.
- For broader search, you can also request a longer sequence of rotation. Each step will generate a snapshot. It is also possible to get an entire 360 degree view in a single command sequence.

""".strip()


reasoner_with_answer_OLD2 = """
### Problem Description

This is a visual 3D modeling problem.

To help you with this, you will have access to a tool called the “imagery module”. More than that, in this task, it is required to resolve it in an "imagery way" (explained below).

The imagery module can perform consistent camera manipulations (object rotation) followed by generating a snapshot image from that angle.

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
    "rationale": "Short description of your rationale and partial conclusion for later reference, the visual evidence you get and what not",
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
  - Each target (each entry in the `commands` list) will generate one composite image.
  - For each target, generate one command or a sequence of rotations. Each rotation step will generate a thumbnail-like snapshot iamge in the composite image. For example, if the comand is "right:10,right:10,right:10" than the composite image for this target will have 3 snapshot images, one for each rotation step. If you request for a rotation with value 0, you can get the current position image.
  - For one target, prefer executing a sequence in a single entry instead of using multiple entries.
* `final_answer`: leave as `null` during investigation/analysis. At the end of the investigation, set the alternative of the problem. This problem has one and only one alternative (A, B, or C). Setting the alternative will finish the problem resolution.

---

### Think with Imagery

**IMPORTANT** For this problem, proceed in an imagery-based way to resolve it as described in the following.

- The images of the objects in this problem (the statement image) are given such that, if you can rotate one to match the other, and they match, then they ARE GUARANTEED to be the same, which means it is not the alternative. On the other hand, for the solution to the problem, you cannot match them regardless of the rotation you perform.
- If you rotate both and they match, it is not conclusive, because there can exist a camera angle view where they are the same, but the objects are not.
- Based on this assumption, the imagery way to resolve the problem is to get clear evidence of whether the objects are identical or not. Which means, find the correct rotation position until it matches the other. For example, match alternative A to the `original` as given in the problem statement image. Or the reverse, which is to rotate the `original` and match the alternative. Again, compare after rotate both don't give any conclusion. The comparision need always to be against the one in the problem statement.
- Because the imagery way is a detailed task, proceed to check each alternative one by one. First focus on A, then B, and then C.
- Rotate the alternative object and try to match the original. If you find a match, OK, you can discard it. If not, mark it as a solution candidate, and proceed to the next.
- **IMPORTANT** For alternatives that you find that is equal (so, is not the answer), generate an evidence image for both, the alternative and the original, with no rotation (ex: left:0), this way you will have as result one snapshopt of both images put side by side, and you can do the final double check.
- **IMPORTANT**. Finding the correct rotation direction is trial and error, or an action-eval loop. You make some rotation, understand the current position, compare it to your target object, and decide the next rotation direction. 
- To have a grasp of the current state, you can ask for a longer sequence, even a 360 view rotation sequence. But, to refine and reach the correct position, you need to proceed with careful incremental rotations. Each rotation step will generate a snapshot, so you can figure out the direction and the current camera angle. Compare it to the target in the statement image, decide the next, and so on.
- Repeat some iterations for each alternative, until get to conclusion for that alternative. 
- **IMPORTANT** Repeat at least **2** turns for each alternative, before proceed to the final answer.
- Make clear in your rationale which alternative you are focusing on; also, if you are doing a broad scan or drill down, have a consistent reasoning process.
- Getting to the correct position may require a number of steps or turns. Repeat and stick with an alternative until you get to a conclusion, and only then proceed to the next one.
- Proceed to double checking and generating even redundant evidences. View in different angles for the purpose of double checking, this is the way imagery way works. After a few redundant and double check steps, proceed to give the final answer.

""".strip()


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

You may issue rotation commands for multiple objects (targets) in a single call.

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
    "current_iteration": 1,
    "rationale": "Summary of your current reasoning — describe what you observed, inferred, or concluded from the available images.",
    "trace": {
        "A": {
            "passed": boolean,
            "verdict": "suspicious" | "discarded" | "unknown",
            "match_evidence_generated": boolean
        }, # repeat to "B" and "C" 
    },
    "plan": "Explain your next steps — which rotations or comparisons you intend to perform next and why."
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

- **`memory.rationale`**:  
  Short description summarizing your reasoning, visual evidence, and partial conclusions. Acts as persistent memory for subsequent turns.

- **`memory.trace`**:  
  Object with the following fields:
  - **`passed`**: boolean indicating if the alternative is passed (already analyzed) or not.
  - **`verdict`**: "suspicious" | "discarded" | "unknown" indicating the verdict of the alternative.
  - **`match_evidence_generated`**: boolean indicating if the match evidence image is generated for the alternative.

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
   - If one can be rotated to match another **exactly**, then both objects are **identical** (meaning that this pair is **not** the correct answer).
   - If no rotation can make them match, they are **different**, and that option is the **solution candidate**.
   - It means also that, if rotate both in some ways, and find a camera angle that they look exactly the same, it is not conclusive at all. For example, you can have a block with 3 cubes and other with 4 cubes stack and you can find an angle where both are seeing as 1 cube only. But, if you rotate the alternative and match the `original` in the initial position (zero rotation), or vice versa, than, this guarantee that they are the same. It means, one of them need to be unrotated from the beginning.
   - Based on that, the strategy to follow is to rotate one side until find a match with the other side.

---

#### **Imagery-Based Procedure**

1. **Work sequentially through all alternatives** (A, then B, then C).

2. For each alternative:
   - Try to find a sequenc of rotation to visually match the original unrotated. 
   - If a match is found, the objects are identical — mark it as **discarded**. 
   - If no match can be found despite all possible rotations, mark it as a **suspicious**.

3. For any alternative found to be identical to the original:
   - Repeat an additional turn to generate an **evidence image**, that is a single cut (**zero rotation** position, e.g. "left:0") of both, the alternative and the target, so that can be compared side by side, where it is expected to looks very similar. This is the **clear evidence**, that gives **visual feedback**, the essence of what will call **magery way**.  

---

#### **Rotation and Observation Process**

- Finding the correct matching rotation is **iterative** and may require a process of **trial and error**:
  - Perform one of a sequence of rotation.
  - Analyze the last position from the genreate image, and have a grasp of the current camera state. Compare with the target and guess which are the directions to make it match to the target.
  - Decide on the next rotation direction and angle based on this evaluation.

- To gain an initial orientation, you may observe a **full 360° rotation sequence**.
- Once familiar with the shape, proceed with **smaller, incremental rotations** to refine and locate the correct matching orientation.
- Each rotation step will produce a **snapshot** image, which will help you visualize current progress and guide the next move.

---

#### **Iteration Strategy and Validation**

- For **each** alternative:
  - Conduct **at least two full analysis passes (turns)** before finalizing any conclusion.
  - State whether you’re performing a **broad scan** (exploratory rotation) or a **drill-down** (fine adjustment phase).

- Perform **redundant and double-checking steps** to validate your conclusion:
  - Compare from multiple angles to ensure reliability.
  - Generate extra evidence or alternate view snapshots as necessary for confirmation.
  - Execute at least 6 iterations before giving the final answer. Think in **imagery way** always require additional steps for visual validation. Correct inference is not enough, generate visual evidence is always necessary.


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


class ToolsBackedImageryReasoner_Eval_05097:

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
