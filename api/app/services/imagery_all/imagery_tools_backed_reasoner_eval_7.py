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
from app.services.imagery_all.stateful_imagery_with_alt import (
    StatefulImageryModuleWithAlt,
)
from app.services.imagery_all.stateful_imagery_with_alt_and_reset_3 import (
    StatefulImageryModuleWithAltAndReset3,
)
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

logger = logging.getLogger(__name__)

hints = """
## HINTS

- Generate a sequence of rotation commands, not just one, to create a better mental model of the underlyning structure.
- **important**: Remember that the concept of `height` or `horizontal`, `vertical`, `left`, `right` is relative, that depends on the camera angle. Don't rely on that in your reasoning. You need to figure out the blocks relative position, that is an **invariant** of the camera position.
- If, in you reasoning you are putting terms like `height`, `horizontal`, this is a indication that you are making wrong assumption.
- use features that don't change with rotation, like the number of boxes and the relative position.
- the resulting color or shades can differ depending on the rendering. Don't depend on that.
- use spatial information of the model, the relative position between the boxes. This is an invariant that don't change!
- what the question is asking is, `assuming that I have a 3D model block composed by a number of individual cubes of size 1, which of the alternatives A, B and C don't correspont to this underlyning 3d model?`. Note that the object can not be reassembled or modified, just rotated (change of the camera angle), and there is in the alternative one that can not be obtained no matter the rotation you do. So, you need to understand the underlyning 3D structure of any of them, and the different views will give you the hint.
- To answer correctly, you need to figure out at least the number of cubes, and how they are assembled.
- **IMPORTANT**: You can be incorrectly identifying the number of cubes at first. Double-check by generating clear perspectives of different angles. 
- **IMPORTANT**: A good evidence would include different angles (not only one) of the `original` AND each of each of the alternatives.
- The rotation command "reset:z" in particular will give a clear view from the top. Most of the problemas are cubes staked on the xy axis, which man, the view from the top will give a clear view to help count the cubes. 
- Here is a sequence of command that give a perspective of the entire structure: "pitch:45,yaw:0,pitch:45,yaw:45,pitch:40,yaw:90,pitch:35,yaw:135,pitch:35,yaw:180,pitch:40,yaw:225,pitch:45,yaw:270,pitch:50,yaw:315,pitch:45,yaw:360,pitch:45"


""".strip()


reasoner_with_answer = """
## Problem Description

This is a **visual reasoning** problem involving the analysis of 3D structures through 2D perspective images.

---

## Task Overview

You are provided with:
- A **2D perspective image** representing an underlying 3D block model.
- A **question** about that model.
- Three **alternatives** labeled **A**, **B**, and **C**.

Your objective is to determine which of the alternatives does **not** correspond to the same 3D structure as the original image.  

This task must be solved **iteratively**.  
Each model interaction represents one iteration in this process. You will receive the conversation **history** containing information from previous iterations.

Although you do **not** have direct access to the underlying 3D model, you can request new perspective images through a helper module called the **imagery module**.  
The imagery module can generate images by applying **rotation commands** to any of the models (original, A, B, or C).  

---

## Iterative Process

In each iteration:
1. Analyze the question, the results from the previous iteration(s), and the available images.
2. Decide:
   - Which model to rotate next (`original`, `A`, `B`, or `C`).
   - Which rotation sequence to apply.
3. Generate your reasoning (“rationale”) and the next rotation command request.

Continue iterating until you can confidently determine your **final answer**.

---

## Output Format

At each iteration, generate your output strictly in the following **JSON format**:

```json
{
  "final_answer": "Provide the answer if you are fully confident. Otherwise leave this null or empty.",
  "rationale": "Explain your reasoning process. Include your sequential rationale number (starting from 1 in the first iteration). Ex: `Rationale 1: ...`. Summarize what you learned from the previous image(s), what you now conclude, and what your next step will be.",
  "rotation_target": "Indicate which model to rotate next: 'original', 'A', 'B', or 'C'.",
  "rotation_sequence": "Provide the sequence of rotation commands to be executed."
}
```

---

## Rotation Command Format

A **rotation sequence** is a list of commands separated by commas.  
Each command has a name and a value:

- **Commands:** "yaw", "pitch", "roll", "reset"
- **Values:**
  - For "yaw", "pitch", and "roll" → an angle in degrees.
  - For `"reset"` → one of "x", "y", "z" or "iso".

**Example:**
```
"yaw:30,yaw:10,pitch:10,roll:10,reset:x,pitch:15,pitch:15"
```

Each command in the sequence generates one **snapshot image**.  
These snapshots will be combined into a **composite image** arranged from top-to-bottom and left-to-right.  
Each snapshot will be annotated, e.g.:
```
"seq:1 command:[yaw:30],pos:[-2.7,8.8,-0.1]_az:0.0°_el:0.0°"
```

Only the **last three iterations' snapshot images** will be visible in the iteration history context.

---

## Rationale Guidelines

When you write your `rationale`, include a sequential label (e.g., “Rationale 1”, “Rationale 2”, etc.).  
Start at 1 for the first iteration and increment by one each subsequent iteration.

Your rationale should include:
- What you have learned so far.
- Any observed structural details (e.g., cube count, spatial arrangement).
- The reasoning behind your next rotation request.
- If applicable, a partial hypothesis or intermediate conclusion.

---

## Methodology and Strategy

- **Validate your conclusions.** Before finalizing an answer, ensure that clear visual evidence supports it.  
  Example: “If I believe it's composed of 5 cubes, I will generate rotations that clearly confirm this structure.”

- It's normal to make **intermediate incorrect assumptions**. Update and refine your reasoning iteratively until convergence.

- Don't hesitate to do a back and forth rotation maneuver, to double check your assumptions.

- Always apply at least one rotation sequence to the **original** and to **each alternative (A, B, C)** before answer the problem.

- **IMPORTANT**: **Before the final answer:**
  - Once you have come to a conclusion, run **2** additional iterations as follows for the double check and evidence generation:
    1. Apply a `reset:z` (top view) rotation to the **selected alternative**, the answer you selected.
    2. Apply a `reset:z` rotation to the **original** image.  
  - In these iteration apply this solo rotation command, to isolate the image for better correctness.
  - Compare both carefully under the same perspective. Here **DON'T** relies on your previous rationales, reset them and think as a new problem, like "ARE THEY SAME"?  
  - If they appear **identical**, I can assure you that your choice **IS INCORRECT**is incorrect; 
  - In this case, even your previous rationales say the inverse, search for a perspective that they appear different. You can repeat the same rotation command to both. This will be your evidence. Without this evidence, you answer is probably WRONG. Don't give the final answer in this situation.
  - For this final validation, starts the rationale as "All right, I suspect that the final answer is *, now let me do the double check by generating a single single top view perspective for both, the answer candidate and the original....", and proceed to generate the perspective. **DON'T ANSWER BEFORE THIS STEP**.

- **Do not rely on color or shading**, as they may change across renderings.

- **Focus on spatial invariants** — features that do not change with rotation:
  - The number of individual cubes.
  - Their relative arrangement and connectivity.

- The final objective is to identify **which alternative (A, B, or C)** cannot be obtained from the original through any rotation.

---

## Hints and Best Practices

- Use multi-step rotations to generate well-rounded views (not just single-axis rotation).
- Avoid describing directions using real-world “top,” “left,” “right,” etc. — these are **camera-relative** and can mislead your reasoning.
- If your reasoning relies on “height” or “horizontal” interpretations, double-check your logic — such terms depend on the viewing angle, not the 3D structure.
- This sequence will give a clear view from the to, rotating 360 degreen a a view from the reverse side.
`reset:z,yaw:90,yaw:90,yaw:90,yaw:90,pitch:180,pitch:180`
- This sequence shows a more global view, but can be overwhelming:
`pitch:45,yaw:0,pitch:45,yaw:45,pitch:40,yaw:90,pitch:35,yaw:135,pitch:35,yaw:180,pitch:40,yaw:225,pitch:45,yaw:270,pitch:50,yaw:315,pitch:45,yaw:360,pitch:45`
- The `reset:z` command provides a top-down view, which is useful for counting blocks and confirming layout consistency.
- The rotation command will be applied from the last state, so to have the same angle for different targets make the reset first. Reset can be one of the axis, or 'iso'".

---

## Goal Recap

Determine which of **A**, **B**, or **C** cannot represent the same 3D model as the **original**, based solely on visual geometry and rotational analysis. Iterate until your conclusion is fully supported by evidence.

---

### Key Requirements
- Always output valid JSON.
- Include step number in `rationale`.
- Never skip contextual reasoning.
- Always generate a clear next action or confirm the final answer only when fully justified.
- Before give you final answer, perform two additional double check iteration generating 'reset:z' perspective for the your answer candidate, and again for the original problem image.
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


class ResponseWithAnswer(BaseModel):
    final_answer: str
    rationale: str
    rotation_sequence: str


def rationale_with_imagery_response(rationales, imagery_response):
    # ensure that rationale and imagery response are in the same length
    assert len(rationales) == len(
        imagery_response
    ), "Rationale and imagery response must be in the same length"

    rationale_with_imagery_resonse = []
    for i in range(len(rationales)):
        rationale_with_imagery_resonse.append(rationales[i])
        # for image, include only the last 3 images
        if i >= len(imagery_response) - 3:
            rationale_with_imagery_resonse.append(imagery_response[i])
    return rationale_with_imagery_resonse


def invalid(cmd_string):
    # Valid command format: "yaw:10,pitch:30,roll:-10"
    allowed_commands = {"yaw", "pitch", "roll", "reset"}
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
        if command != "reset":
            try:
                float(value)
            except Exception:
                traceback.print_exc()
                return True
        else:
            if value not in ["x", "y", "z", "iso"]:
                return True
    return False


class ToolsBackedImageryReasoner_Eval7:

    # REASONING_MODEL = 'chatgpt-4o-latest'
    # REASONING_MODEL = 'gpt-5.1-chat-latest'
    # REASONING_MODEL = "gemini-3-pro-preview"
    REASONING_MODEL = "gpt-5.1"

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
        imagery = StatefulImageryModuleWithAltAndReset3(
            bounds_map, off_screen=True, show_grid=True
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
            imagery_response = []
            while iter_count <= MAX_ITERATION:

                # call reasoner module with imagery module aware prompt, and last image if exists
                print(
                    f"\n=================== Call REASONING model {iter_count} ==================\n"
                )

                if iter_count <= MIN_ITERATION:
                    reasoner_system_message = reasoner_with_answer
                    response_schema = ResponseWithoutAnswer.model_json_schema()
                else:
                    reasoner_system_message = reasoner_with_answer
                    response_schema = ResponseWithAnswer.model_json_schema()

                reasoning_retry_cout = 5
                valid = False
                while reasoning_retry_cout > 0:
                    reasoning_retry_cout -= 1
                    response, _, _, _ = await call_llm(
                        [{"role": "system", "content": reasoner_system_message}]
                        + freeze_history
                        + rationale_with_imagery_response(rationales, imagery_response),
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
                    rotation_sequence, rotation_target = response_dict.get(
                        "rotation_sequence"
                    ), response_dict.get("rotation_target")
                    if not rotation_sequence or invalid(rotation_sequence):
                        print(
                            f"Invalid or no rotation_sequence found. RETRY {reasoning_retry_cout}"
                        )
                        continue

                    # no final answer, valid rotatino sequence. Valid output!
                    valid = True
                    break

                if not valid:
                    raise Exception(
                        f"Invalid or no rotation_sequence found. {response}"
                    )

                print(
                    f"rotation_target: {rotation_target}, rotation sequence:{rotation_sequence}"
                )

                # -- continues iteration --
                # build history for reasoning
                rationales.append({"role": "assistant", "content": response})

                # call imagery
                print(
                    f"\n==[{cls.__name__}]================= Call IMAGERY {iter_count} {rotation_sequence} ==================\n"
                )
                image_path = imagery.run_sequence_and_save_image(
                    rotation_target, rotation_sequence
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

                else:
                    raise Exception(f"Image not generated {response}")

                # imagery history
                imagery_response.append({"role": "assistant", "image_url": image_url})

                iter_count += 1

            # exceed iterations, call without system message
            print(
                f"\n=={cls.__name__}================= Exceeded MAX. Reasoning model LAST call ==================\n"
            )
            response, _, _, _ = await call_llm(
                [{"role": "system", "content": reasoner_for_final_answer}]
                + freeze_history
                + rationale_with_imagery_response(rationales, imagery_response),
                cls.REASONING_MODEL,
                options,
            )

            response_dict = parser_json(response)
            return response_dict.get("final_answer", response), chat_history, None

        finally:
            imagery.close()
