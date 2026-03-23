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
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

logger = logging.getLogger(__name__)

# memo:
# this is a prompt with CoT (Chain of Thought) for the reasoning process.

prompt_for_reasoner = """
### **System Architecture: Dual Coding Cognitive Agent**

**Role:** You are the **Cognitive Executive Function** (Reasoning).
**Tool:** You control an external **Visual Cortex** (Imagery Module).

**The Challenge:**
Visual perception is unreliable. A 2D image is a lossy compression of 3D reality. To solve spatial problems, you cannot rely on "looking"; you must actively **construct a 3D Mental Model** through experimentation.

### **Cognitive Protocols (Hard Constraints)**

To override your bias for "fast thinking," you must strictly adhere to these protocols. Failure to follow them causes a cognitive error (hallucination).

1.  **Inhibition Control (The 4-Turn Rule):**
    *   Your mental model is unstable in the beginning.
    *   **Constraint:** You are **FORBIDDEN** from finalizing a decision (`final_answer`) before **Iteration 4**.
    *   *Why?* You need time to accumulate spatial data.

2.  **Selective Attention (The "Deep Dive" Rule):**
    *   Multitasking degrades spatial resolution.
    *   **Constraint:** In at least one iteration (Phase 2), you must target **ONLY ONE** object (e.g., Target `B` only). Ignore the `original` and other candidates during that turn to focus your entire "cognitive buffer" on mapping that single object's hidden geometry.

3.  **Verification Lock:**
    *   You cannot conclude based on intuition.
    *   **Constraint:** You may only provide a `final_answer` after executing a "Visual Proof" (Phase 3) where you align the `original` and the `suspect` to the **exact same novel angle** (e.g., both from Top-Down).

---

### **Investigation Phases (The Mental Workflow)**

Follow this cognitive roadmap based on your iteration count:

**Phase 1: Broad Scanning (Iterations 1-2)**
*   **Cognitive State:** Confusion.
*   **Goal:** Identify which candidate (`A`, `B`, or `C`) generates "Cognitive Dissonance" (looks slightly wrong).
*   **Action:** Rotate `original` and candidates broadly to spot gross differences.
*   **Output:** `final_answer`: `null`.

**Phase 2: Focal Attention / Deep Dive (Iterations 3-5)**
*   **Cognitive State:** Focused Investigation.
*   **Goal:** Build a dense 3D map of the most ambiguous object.
*   **Action:** Pick ONE target (the most confusing one). Generate a **long sequence** of rotations (4+ commands) for that SINGLE target to see it from every side.
    *   *Example:* `target: "B", sequence: "reset:iso, yaw:90, pitch:45, yaw:45, pitch:-90"`
*   **Output:** `final_answer`: `null`.

**Phase 3: Visual Verification (Iteration 6+)**
*   **Cognitive State:** Conclusion.
*   **Goal:** Validate the hypothesis.
*   **Action:** Perform the "Kill Shot." Set `original` and `Candidate` to a standard view (e.g., `reset:z` or `reset:y`) in the same turn to compare their profiles directly.
*   **Output:** If the profiles match/mismatch as expected, set `final_answer`.

---

### **Imagery Module Interface**
You act as the puppet master for the Imagery Module.
*   **Stateful:** The imagery module remembers previous rotations.
*   **Commands:** `yaw` (orbit), `pitch` (tilt), `roll` (spin), `reset` (iso, x, y, z).
*   **Tactics:**
    *   To understand shape: Use `yaw` to rotate around it.
    *   To check height/depth: Use `pitch`.
    *   To restart the mental map: Use `reset:iso`.

---

### **Output Format**

You must explicitly track your "Mental State" to ensure you are following the protocols.

```json
{
  "mind_state": {
    "current_iteration": integer,
    "current_phase": "Broad Scanning | Focal Attention | Visual Verification",
    "spatial_dissonance": "Which candidate currently feels 'wrong' and why? (e.g., 'Model B seems to lack the rear protrusion present in Original')",
    "attentional_focus": "Which object are we drilling down on this turn?",
    "protocol_check": "Have I passed Iteration 4? [Yes/No]"
  },
  "commands": [
    {
      "target": "original|A|B|C", 
      "rotation_sequence": "command:value, command:value..."
    }
  ],
  "final_answer": "Null until Phase 3 validation is complete."
}
```

**Context:** You are currently at Iteration {{iteration_number}}.
**Trigger:** Analyze the visual input. Determine your Phase. Execute the next cognitive step.
""".strip()

logger = logging.getLogger(__name__)


class ResponseWithoutAnswer(BaseModel):
    rationale: str
    rotation_sequence: str


class TargetAndCommand(BaseModel):
    target: str
    rotation_sequence: str


class ResponseForReasoner(BaseModel):
    thought_process: dict
    final_answer: str | None
    commands: list[TargetAndCommand] | None


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


class ToolsBackedImageryReasoner_Eval96:

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
        imagery = StatefulImageryModule4NoShadowPerspective(
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
                logger.info(
                    f"\n=================== Call REASONING model {iter_count} ==================\n"
                )

                # if iter_count <= MIN_ITERATION:
                #     reasoner_system_message = reasoner_with_answer
                #     response_schema = ResponseWithoutAnswer.model_json_schema()
                # else:
                reasoner_system_message = prompt_for_reasoner
                response_schema = ResponseForReasoner.model_json_schema()

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
                        logger.info(f"Not a dictionary. RETRY {reasoning_retry_cout}")
                        continue

                    final_answer = response_dict.get("final_answer")
                    if final_answer:
                        logger.info('"final_answer" found. Finish')
                        return final_answer, chat_history, None

                    # if there is no instruction to imagery, finish
                    commands = response_dict.get("commands")
                    if not commands:
                        logger.info(f"No commands found. RETRY {reasoning_retry_cout}")
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
                    logger.info(
                        f"\n==[{cls.__name__}]================= Call IMAGERY {command.get('target')} {command.get('rotation_sequence')} ==================\n"
                    )
                    rotation_sequence = command.get("rotation_sequence")
                    if isinstance(rotation_sequence, list):
                        rotation_sequence = ",".join(rotation_sequence)

                    image_path = imagery.run_sequence_and_save_image(
                        target, rotation_sequence
                    )
                    logger.info(f"==[{cls.__name__}] image_path: [{image_path}]: <<")
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
                        logger.info(f"image_url: [{image_url}]: <<")
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
            logger.info(
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
