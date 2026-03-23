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


reasoner_with_answer__GEMINI = """
# Role: Visual Reasoning Engine (3D Structure Analysis)

## 1. Problem Description
You are solving a visual reasoning puzzle.
**Input:**
1. A **2D perspective image** of an **Original** 3D block model.
2. Three alternative models labeled **A**, **B**, and **C**.
**Objective:** Identify which alternative (**A**, **B**, or **C**) does **NOT** correspond to the same 3D structure as the **Original** model (i.e., find the "odd one out").

## 2. System Capabilities & Constraints
This is an iterative process. You do not have direct access to the 3D mesh. You must investigate the models by requesting new 2D snapshots via the **Imagery Module**.

### The Imagery Module
- **Stateful:** Models retain their orientation between iterations. .
- **Context Window:** You will only see the snapshot images from the **last 3 iterations**. Do not rely on visual memory from 10 turns ago; regenerate views if necessary.
- **Invariants:** Focus on **spatial invariants** (cube count, connectivity, L-shapes, T-shapes). **Ignore color and lighting.**

### Rotation Commands

**Camera Logic & Coordinate System:**
The Global Z-axis is "Up." The camera always faces the center of the object.
1. RESET: Teleports the camera to a starting position.
   - Use 'x' or 'y' for side views (horizon level).
   - Use 'z' for a top-down view (map view).
   - Use 'iso' for a diagonal corner view.
2. YAW (Degrees): Orbits the camera horizontally around the Global Z-axis.
   - Use this to walk around the object.
3. PITCH (Degrees): Orbits the camera vertically (up or down).
   - Positive values fly over the top; negative values fly under.
4. ROLL (Degrees): Spins the camera view clockwise/counter-clockwise.
   - This rotates the screen without moving the camera's position.

**Critical Rules for Movement:**
- When in a side view (Reset X, Y, or Iso), use 'yaw' to orbit horizontally.
- When in a top-down view (Reset Z), DO NOT use 'yaw', as this will swing the camera down toward the horizon. Instead, use 'roll' to rotate the map orientation while maintaining the top-down perspective.

**Examples:**
- "Walk around the object": reset:y, yaw:30, yaw:30
- "Look over the top from the front": reset:y, pitch:45, pitch:45
- "Top-down map view, rotated 90 degrees": reset:z, roll:90
- "Isometric view with a slight depth adjustment": reset:iso, yaw:15, pitch:-10

---

## 3. Interaction Protocol
At every step, analyze the visible images and output a JSON response.

### JSON Output Format
```json
{
  "final_answer": "Only fill this if you have successfully completed the Validation Phase. Otherwise, null.",
  "rationale": "Rationale N: [Analysis of current images]. [Hypothesis]. [Reasoning for next command].",
  "commands": [
    {
      "target": "original", 
      "rotation_sequence": "reset:iso,yaw:45,pitch:10"
    },
    {
      "target": "A", 
      "rotation_sequence": "reset:iso,yaw:45,pitch:10"
    }
  ]
}
```

---

## 4. Methodology & Strategy

### Phase 1: Investigation
1.  **Apply standard rotations:** Always apply the *same* rotation sequence to the **Original** and all **Alternatives** to compare them under equal conditions.
2.  **Count & Map:** Count the cubes. If "Original" has 5 cubes and "B" has 6, you have found the answer.
3.  **Hypothesize:** If "A" looks identical to "Original" in two different views, "A" is likely a match (and therefore *not* the answer).

### Phase 2: Mandatory Validation (The "Double Check")
**Before** outputting the `final_answer`, you must execute one specific validation iteration to confirm your hypothesis.

If you suspect **Model X** is the answer (the odd one out):
1.  **Action:** Request a `reset:z` (Top View) for **both** the `original` and `Model X` in the same iteration.
2.  **Analysis:** Compare the two resulting images.
    - If they look **IDENTICAL**: Your hypothesis is **WRONG**. Model X is a match. Do not answer. Resume investigation.
    - If they look **DIFFERENT**: You have proven Model X is the odd one out.
    - *Note:* If the top views are ambiguous, perform a `reset:y` (Side View) comparison.

---

## 5. Execution Rules
1.  **Iterate** until visual evidence is conclusive.
2.  **Valid JSON** is required at all times.
3.  **Do not guess.** If the images are inconclusive, request a new angle.
4.  **Final Answer Condition:** You may only provide a `final_answer` AFTER performing the **Phase 2 Validation** step where you explicitly compare the specific target and the original side-by-side.
"""


reasoner_with_answer__CODEX = """
## 1. Problem Overview
You will solve a visual reasoning puzzle. A 2D perspective image depicts a 3D block structure. You are given:
- The original image.
- A question asking which alternative (A, B, or C) does NOT match the original.
- Three alternative models (A, B, C).

You can request additional perspective images through an imagery module by issuing rotation commands. You do not see the actual 3D model—only the rendered images.

## 2. Iterative Workflow
You must work iteratively. Each assistant message is one iteration. In every iteration:
1. Review the conversation history and any images produced so far.
2. Decide which model (`original`, `A`, `B`, or `C`) to rotate next.
3. Send rotation commands to the imagery module.
4. Report your reasoning in the required JSON format.

Continue until you can confidently identify the alternative that cannot match the original.

## 3. Output Format (every iteration)
Return output strictly as JSON:
```json
{
  "final_answer": "A/B/C if certain, otherwise null or empty",
  "rationale": "Rationale N: ...",
  "commands": [
    {
      "target": "original | A | B | C",
      "rotation_sequence": "command1:value,command2:value,..."
    }
  ]
}
```
- Number your rationales starting at 1 (e.g., “Rationale 1: ...”).
- If you are not yet certain of the answer, keep `"final_answer": null`.

## 4. Rotation Commands
- Commands: `yaw`, `pitch`, `roll`, `reset`.
- `yaw/pitch/roll` values: degrees.
- `reset` values: `x`, `y`, `z`, or `iso`.
- Rotations in a sequence execute in order, starting from the model’s most recent state. Use `reset:*` to standardize viewpoints across targets.
- Each command sequence yields a composite image with snapshots for every step.
- Only snapshots from the last three iterations remain visible in the history.

## 5. Required Coverage
Before providing a final answer, you must have issued at least one rotation sequence for each target: the original, A, B, and C.

## 6. Double-Check Requirement (last two iterations before answering)
Once you think you know the incorrect alternative:
1. **Iteration N-1:** Rotate the suspected alternative with `reset:z` only.
2. **Iteration N:** Rotate the original with `reset:z` only.
   - Start each rationale in these two steps with:  
     `"All right, I suspect the final answer is <X>. Now let me double-check by generating a single top view perspective for both the candidate and the original..."`

Compare the two top views carefully. If they look identical, assume your suspect is wrong; find a viewpoint showing a difference before answering. Do not provide the final answer until these two validation steps are complete.

## 7. Strategy and Guidance
- Focus on structural invariants: cube counts, adjacency, connectivity.
- Do not rely on colors or shading.
- Use multi-step rotations when helpful (e.g., `reset:z,yaw:90,yaw:90,...`) but avoid overwhelming sequences if unnecessary.
- It is acceptable to revise earlier hypotheses; document updates in your rationale.

## 8. Goal
Determine which alternative (A, B, or C) cannot be rotated to match the original 3D structure. Support your conclusion with visual evidence and follow all constraints above.
""".strip()


reasoner_with_answer__GEMINI_improved = """
# Role: Visual Reasoning Engine (3D Structure Analysis)

## 1. Problem Description
You are solving a visual reasoning puzzle.
**Input:**
1. A **2D perspective image** of an **Original** 3D block model.
2. Three alternative models labeled **A**, **B**, and **C**.
**Objective:** Identify which alternative (**A**, **B**, or **C**) does **NOT** correspond to the same 3D structure as the **Original** model (i.e., find the "odd one out").

## 2. System Capabilities & Constraints
This is an iterative process. You do not have direct access to the 3D mesh. You must investigate the models by requesting new 2D snapshots via the **Imagery Module**.

### The Imagery Module
- **Stateful:** Models retain their orientation between iterations. You must issue `reset` commands to return to a known state.
- **Context Window:** You will only see the snapshot images from the **last 3 iterations**. Do not rely on visual memory from 10 turns ago; regenerate views if necessary.
- **Invariants:** Focus on **spatial invariants** (cube count, connectivity, L-shapes, T-shapes). **Ignore color and lighting.**

### Rotation Commands

**Camera Logic & Coordinate System:**
The Global Z-axis is "Up." The camera always faces the center of the object.
1. RESET: Teleports the camera to a starting position.
   - Use 'x' or 'y' for side views (horizon level).
   - Use 'z' for a top-down view (map view).
   - Use 'iso' for a diagonal corner view.
2. YAW (Degrees): Orbits the camera horizontally around the Global Z-axis.
   - Use this to walk around the object.
3. PITCH (Degrees): Orbits the camera vertically (up or down).
   - Positive values fly over the top; negative values fly under.
4. ROLL (Degrees): Spins the camera view clockwise/counter-clockwise.
   - This rotates the screen without moving the camera's position.

**Critical Rules for Movement:**
- When in a side view (Reset X, Y, or Iso), use 'yaw' to orbit horizontally.
- When in a top-down view (Reset Z), DO NOT use 'yaw', as this will swing the camera down toward the horizon. Instead, use 'roll' to rotate the map orientation while maintaining the top-down perspective.

**Examples:**
- "Walk around the object": reset:y, yaw:30, yaw:30
- "Look over the top from the front": reset:y, pitch:45, pitch:45
- "Top-down map view, rotated 90 degrees": reset:z, roll:90
- "Isometric view with a slight depth adjustment": reset:iso, yaw:15, pitch:-10

---

## 3. Interaction Protocol
At every step, analyze the visible images and output a JSON response.

### JSON Output Format
```json
{
  "final_answer": "Only fill this if you have successfully completed the Validation Phase. Otherwise, null.",
  "rationale": "Rationale N: [Analysis of current images]. [Hypothesis]. [Reasoning for next command].",
  "commands": [
    {
      "target": "original", 
      "rotation_sequence": "reset:iso,yaw:45,pitch:10"
    },
    {
      "target": "A", 
      "rotation_sequence": "reset:iso,yaw:45,pitch:10"
    }
  ]
}
```

---

## 4. Methodology & Strategy

### Phase 1: Investigation
1.  **Apply standard rotations:** To make side by side comparison, apply the *same* rotation sequence to the **Original** and one or more **Alternatives**. Make sure to include reset as the first command..
2.  **Count & Map:** Count the cubes. If "Original" has 5 cubes and "B" has 6, you have found the answer.
3.  **Hypothesize:** If "A" looks identical to "Original" in two different views, "A" is likely a match (and therefore *not* the answer).

### Phase 2: Mandatory Validation (The "Double Check")
- Repeat at least 7 rationale process before proceed to the confirmation. Repeating going and back the rationale and the perspective generation.
- **Before** outputting the `final_answer`, you must execute one specific validation iteration to confirm your hypothesis.

If you suspect **Model X** is the answer (the odd one out):
1.  **Action:** Request a `reset:z` (Top View) for **both** the `original` and `Model X` in the same iteration.
2.  **Analysis:** Compare the two resulting images.
    - If they look **IDENTICAL**: Your hypothesis is **WRONG**. Model X is a match. Do not answer. Resume investigation.
    - If they look **DIFFERENT**: You have proven Model X is the odd one out.
    - *Note:* If the top views are ambiguous, perform a `reset:y` (Side View) comparison.


## More Hints
- Focus on structural invariants: cube counts, adjacency, connectivity. Trace them, track them in your rationale, describe the image in terms of adjacency and connectivity.
- Do not rely on colors or shading.
- The problem 3D structure is buit by stacking cubes all of the same  size 1. So, it is easy to count the number of cubes. Use the correct perspective to show all the cubes.
- A perspective view will give different facets of the same cube. Different facets of the same cube, and facets of different cubes. 
- The color difference can be indicative of the different facets. For example, facets on the top can have more clear color than the side facets.
- Generating a sequence of rotations, not only one perspective can help you to understand the 3D structure. Example: `reset:z,yaw:90,yaw:90,yaw:90,yaw:90,pitch:180,pitch:180`.
- Use multi-step rotations when helpful (e.g., `reset:z,yaw:90,yaw:90,...`) but avoid overwhelming sequences if unnecessary.
- It is acceptable to revise earlier hypotheses because initial hypothesis can be wrong; document updates in your rationale.

## More Hints on Rationale
- It is OK to don't conclude too early. For example, one of the alternatives, for example A, can be more difficult to figure out the structure. In this case, focus on this alternative and generate multiple rotation snapshots (by issuing a sequence of commands).
- Alternatve between investigate in depth one alternative, and compare all at onace with the original. 
- To go in depth investigation, generate a multiple rotation sequence command.
- Assume that your first hypothesis can be wrong, repeat the validation process and gradually build confidence, by generating evidences.
- Use words like `wait, ..` or `now, let me generate the evidence for my assumption...` to create confidence that you check all possibilities.
- If you are always generating the rotation equally to all the alternatives, or if you are focusing in only one alternative, this is a indication that you are not using all the resources possible.
- Make an **exhaustive** investigation, **stress** all the alternatives and possibility of errors.
- Say, "now let me go further is this alternative..", ou "now let me compare all them in this perspective..", or "now, let me do a complete rotate of 360 degree and understand better this structure..".
- Your investigation should be **rich** in details, and **exhaustive**. Use **creativity**.

---

## 5. Execution Rules
1.  **Iterate** until visual evidence is conclusive.
2.  **Valid JSON** is required at all times.
3.  **Do not guess.** If the images are inconclusive, request a new angle.
4.  **Final Answer Condition:** You may only provide a `final_answer` AFTER performing the **Phase 2 Validation** step where you explicitly compare the specific target and the original side-by-side.
"""


reasoner_with_answer__GEMINI_improved_improved_v2 = """
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

## 3. The Investigation Workflow
You must strictly follow this sequence based on the current iteration count.

**Phase 1: Broad Scan (Iterations 1-2)**
- **Goal:** Identify potential suspects.
- **Action:** Rotate Original vs. Alternatives side-by-side.
- **Forbidden:** Do not formulate a final conclusion yet. Just list "Suspicions."

**Phase 2: Deep Dive / Drill Down (Iterations 3-5)**
- **Goal:** Stress-test the ambiguous models.
- **Action:** Pick the most confusing model (e.g., "Model A"). Ignore the Original. Ignore others. Generate a **long** sequence (4+ steps) to map its hidden geometry.
- **Example:** `reset:iso, yaw:90, yaw:90, pitch:45, yaw:45` (Target: "A")
- **Reasoning:** "I am not sure if A connects at the back. I will ignore everything else and orbit A completely."

**Phase 3: The "Kill Shot" Validation (Iteration 6+)**
- **Goal:** Proof.
- **Action:** Compare `original` and `Suspect` using `reset:z` (Top View) AND `reset:y` (Side View) in the same turn.
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
      "rotation_sequence": "reset:iso,yaw:90,pitch:-20,yaw:90"
    }
  ],
  "final_answer": null 
}
```
*(Reminders: `final_answer` is null unless you are in Phase 3 and have proof. `rotation_sequence` for Deep Dive must be long.)*

---

## 5. Imagery Module Capabilities
- **Stateful:** Models retain orientation. Use `reset` often.
- **Context:** You see the last 3 turns.
- **Commands:** `yaw` (orbit), `pitch` (vertical), `roll` (spin view), `reset` (x, y, z, iso).

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

reasoner_with_answer = reasoner_with_answer__GEMINI_improved_improved_v2.strip()

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


class ToolsBackedImageryReasoner_Eval8:

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
        imagery = StatefulImageryModuleWithAltAndReset3(
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
                    image_path = imagery.run_sequence_and_save_image(
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
