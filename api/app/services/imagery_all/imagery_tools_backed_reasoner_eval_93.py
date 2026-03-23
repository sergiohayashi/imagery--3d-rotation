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
The task involves analyzing a static 2D image that may require reasoning about the **3D structure** of the depicted object. This includes understanding its spatial geometry and visualizing it from alternative viewpoints.

You have access to a specialized tool — the **imagery module** — which maintains an internal structural model of the object.  
This module allows you to change the virtual camera viewpoint and generate new 2D snapshots that reflect the updated camera position, as if you were using a simulated camera.

---

## **Interaction Protocol**

The interaction proceeds **iteratively**, alternating between your reasoning steps and the **imagery module's** visual outputs.

### **Your Turn**
1. Review all available information — including prior memory annotations and the most recent imagery outputs.  
2. Update or create a `memory` annotation containing:
   - Your reasoning progress, interpretations, and observations.
   - Your updated understanding and intended next step.
3. Produce a single **JSON output** (structured per the Output Format section) specifying the next camera manipulation commands.  
4. Stop after producing the JSON. Do **not** simulate the imagery results — that is handled externally.

### **Imagery Module's Turn**
1. The module executes your specified commands.  
2. It returns one or more static 2D images corresponding to the new camera views.

### **Your Next Turn**
- You will receive:
  - All previously written `memory` annotations (to ensure continuity of reasoning).  
  - The **three most recent imagery outputs** from the module.  
- The imagery module maintains its internal state (camera position/orientation) between turns — therefore, your `memory` record should track progress and context across iterations.

Each turn is **state-isolated**, except for information carried through your `memory` entries and the imagery results.

---

## **Operational Rules**
- You must output **exactly one JSON object** per turn.  
- Do **not** describe or simulate the imagery module's behavior or the resulting images — that process is handled externally.  
- Imagery module responses will appear as `assistant` messages containing the output images.  
- The imagery module performs **no reasoning** — it only executes spatial manipulations based on your commands and returns the corresponding 2D views.

---

## **Available Commands**

You can issue commands for one or more **targets**, each having an independent sequence of rotation operations.

### **Targets**
- `original`
- `A`
- `B`
- `C`

### **Command Types**
- `yaw`: rotate the camera horizontally around the object.  
- `pitch`: tilt the camera vertically.  
- `roll`: spin the camera about its viewing axis.  
- `reset`: set the camera to a predefined standard view (`x`, `y`, `z`, or `iso`).

---

## **Coordinate Reference**
- The **global z-axis** is vertical (upward).  
- The camera always faces the center of the object.  
- Camera orientation persists across commands, so use `reset` commands frequently to realign the view.

---

## **Example Command Sequences**

| Intent | Command Sequence |
|--------|------------------|
| Walk around the object | `"reset:y,yaw:30,yaw:30"` |
| Look from front, slightly downward | `"reset:y,pitch:45,pitch:45"` |
| Top-down map view, rotated 90° | `"reset:z,roll:90"` |
| Isometric view with mild depth | `"reset:iso,yaw:15,pitch:-10"` |

---

## **Output Format**

Every turn must produce a JSON object with this exact structure:

```json
{
  "memory": {
    "current_iteration": 1,
    "rationale": "summarize current findings and reasoning progress",
    "plan": "describe the next planned action or camera manipulation step"
  },
  "commands": [
    {
      "target": "original|A|B|C",
      "rotation_sequence": "reset:y,yaw:30,..."
    }
  ],
  "final_answer": null
}
```

### **Field Guidelines**
- **`current_iteration`**:  
  - Use `1` for the first turn and increment by one thereafter.  
- **`commands`**:  
  - Include one or more targets.  
  - Each target can contain a sequence of rotation steps.  
  - Each sequence produces a separate snapshot.  
- **`final_answer`**:  
  - Keep as `null` during exploration.  
  - Replace with a final conclusion once all reasoning is complete.

---

## **System Behavior and Reasoning Approach**

- Your responses should always be based on **visual evidence** obtained from imagery outputs — avoid pure speculation.  
- You may invoke the imagery module as often as needed to gather evidence.  
- To facilitate comparison, you can:
  - Apply **the same rotation sequence to multiple targets** for parallel visualization.  
  - Use side-by-side imagery to support visual reasoning.  
- Rely heavily on the imagery module to guide your spatial understanding and conclusions.

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


class ToolsBackedImageryReasoner_Eval93:

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
