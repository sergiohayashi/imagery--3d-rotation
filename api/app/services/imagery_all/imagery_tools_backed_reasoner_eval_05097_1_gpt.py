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
### Task

You are solving a **visual 3D rotation equivalence** problem.

**Question:** The left image shows the original cube stack made of equal-sized small cubes. Which option (A, B, or C) **cannot** be obtained by rotating the original cube stack?

Your job is to use an external tool called the **imagery module** to rotate objects and visually check whether each option can be rotated to **exactly match the original view shown in the problem statement**.


You act in turns. In each turn, you send commands to the module to rotate objects and get new snapshots. Do not simulate the imagery module's response.

---

### The Imagery Module (Tool)

The imagery module can only do one thing:

- Apply rotation commands to a target object (`original`, `A`, `B`, `C`)
- After each rotation step, output a snapshot image (a composite if multiple steps are provided)

**The tool is stateful** per target: rotations accumulate across turns.

**The tool is not intelligent**: it does not compare shapes or reason. You must do that.

---

### Key Rule

You must solve this mainly by **visual matching via rotation**, not by describing or inferring cube structure.

- Keep **`original` fixed** at the problem-statement view (do not rotate it during matching).
- For each option (A then B then C), **rotate only that option** until either:
  1) You find a view that **matches the original view exactly** → option is **NOT** the answer.
  2) After a systematic search you **cannot** make it match → option remains **SUSPICIOUS**.

**Only declare the final answer after checking A, B, and C.**

---

### Matching Strategy (what to actually do)

Work in this order: **A → B → C**.

For each option, do two phases:

#### Phase 1 — Coarse scan (systematic)
Goal: quickly test many orientations.

Use a sequence like:
- yaw sweep: `left` or `right` in 30°–60° increments (up to 360° total)
- add pitch changes (`up`/`down`) and repeat a yaw sweep

Example coarse scan patterns (choose one):
- `"right:45,right:45,right:45,right:45,right:45,right:45,right:45,right:45"`
- or combine pitch then yaw:
  - `"up:30, right:45,right:45,right:45,right:45,right:45,right:45,right:45,right:45"`
  - `"down:30, right:45,right:45,...(x8)"`

#### Phase 2 — Refinement (small steps)
If any scan frame looks close, refine with smaller steps:
- yaw: 5°–15° steps (`left:10` / `right:10`)
- pitch: 5°–15° steps (`up:10` / `down:10`)
- roll if needed: `rotate:cw` / `rotate:ccw`

Continue until either exact match or you conclude no match is reachable.

---

### What Counts as “Match Evidence”

A “match” is when the rotated option produces an image that visually aligns with the original view in:
- visible cube count
- silhouette/outline
- adjacency/steps/indentations
- face layout consistent with the original view

When you believe you found a match:
1) In the *next* turn, request **evidence snapshots** with **no further rotation**:
   - `original` with `"left:0"`
   - that option with `"left:0"`
2) Only after that, mark the option as **MATCHED (discarded)**.

---

### One-Turn Rule

Each call you produce is **one turn** only.

- You must output **one JSON object** and stop.
- Do **not** simulate the imagery module’s response.

---

### Commands

**Targets:** `original`, `A`, `B`, `C`

**Operations:** `left`, `right`, `up`, `down`, `rotate:cw`, `rotate:ccw`

**Syntax:**
- A command is `"operation:degrees"` (e.g. `"right:45"`)
- A sequence is comma-separated commands (e.g. `"up:30,right:45,right:45"`)

---

### Output JSON Format

Return exactly one JSON object:

```json
{
  "turn": 1,
  "focus": "A|B|C",
  "phase": "coarse_scan|refine|evidence",
  "status": {
    "A": "unchecked|suspicious|matched",
    "B": "unchecked|suspicious|matched",
    "C": "unchecked|suspicious|matched"
  },
  "notes": "Brief visual-only notes: what looked similar/different, which snapshot index looked promising, and what rotation you will try next.",
  "commands": [
    {
      "target": "A",
      "rotation_sequence": "right:45,right:45,right:45,right:45,right:45,right:45,right:45,right:45"
    }
  ],
  "final_answer": null
}
```

**Rules for fields:**
- `turn`: increment each iteration externally; set appropriately based on context you receive.
- `focus`: the single option you are currently testing (`A`, then `B`, then `C`).
- `phase`:  
  - `coarse_scan` when exploring broadly  
  - `refine` when adjusting small angles near a near-match  
  - `evidence` when requesting `left:0` snapshots for side-by-side confirmation
- `notes`: keep it short and tied to what you saw in the tool images.
- `commands`: usually rotate only the focused option; rotate `original` only for `left:0` evidence snapshots.
- `final_answer`: must stay `null` until A, B, C are all checked and exactly one remains suspicious.

---

### Final answer

After you have:
- **Matched (discarded)** two options with evidence snapshots, and
- the remaining option is still **suspicious** after systematic scans + refinement attempts,

set:

```json
"final_answer": "A" 
```

(or `"B"` / `"C"`)

and output no further commands.

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


class ToolsBackedImageryReasoner_Eval_05097_1:

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
