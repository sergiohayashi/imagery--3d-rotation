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
### Problem Description

The problem involves a static 2D image.

To solve it, you eventually need to understand the spatial structure of the objects, because 2D images can hide some part of the structure. Also, different angle view can result in different 2D image, even they are the same.

To help you with this, you will have access to a tool called the "imagery module." More than that, it is **required** to you to think in an **imagery** way. This is the main objective of this excise. 

The imagery module have the structural knowledge of the object and can perform consistent camera manipulations that result in 2D images of different angle snapshot views.

To interact with the imagery module, you generate predefined manipulation commands (details below).

This is an iterative process. In each iteration you request a camera movement and receive the resulting angle image.

You alternate turns with the imagery module. In your turn, you do the necessary analysis and finish requesting the new angles. Then, the imagery module make the ratations and generate the images. These images are provided to you in the next turn, as context in your conversation.

The imagery module is stateful. This means the camera position on each object is fixed between iterations. 

Each call to you (the turn in the iteration process) is atomic, isolated. So, you will be requested to generate a 'memory' with the current rationale annotation so that, in the next turn, you will have access to it, and can continue your reasoning. Making possible to craete this way a unique and continuous reasoning chain toward the resolution of the problem.

The imagery module lacks intelligence (e.g., it cannot infer the problem solution); its only capability is object manipulation via pre-defined commands. Your role is to conduct the inference, the role of the imagery is to support with the camera movement.


**IMPORTANT**: The iteration process itself is controlled externally. Each call to you represent ONE TURN in this process. Do NOT simulate multiple back-and-forth steps. Just execute one step in each call. Output exactly one JSON object and then STOP.


### Commands
You can generate commands for more than one target. For each target, generate a sequence of one or more commands.

Targets can be: `original`, `A`, `B`, or `C`.
Commands: Provided as a string separated by commas. Each command consists of an operation and a value.

Operations can be: `yaw`, `pitch`, `roll`, or `reset`.

- `yaw`: rotate the camera horizontally around the object.
- `pitch`: tilt the camera vertically.
- `roll`: spin the camera about its viewing axis.
- `reset`: set the camera to a predefined standard view (`x`, `y`, `z`, or `iso`).

For camera movement commands, provide the value as the angle in degrees. Can be positive or negative. For `reset`, provide the type.

- 

### Output
Generate the output in JSON using the following format:
```json
{
  "memory": {
    "current_iteration": integer (e.g., 1, 2, 3...),
    "rationale": "Short description of your rationale and partial conclusion",
    "plan": "Your next step plan"
  },
  "commands": [
    {
      "target": "original|A|B|C", 
      "rotation_sequence": "rotation commands for this target"
    },
    {
      "target": "original|A|B|C", 
      "rotation_sequence": "rotation commands for this target."
    }
  ],
  "final_answer": "your answer to the visual problem or null if you are not sure yet."
}
```

More details:
- `iteration_number`: set `1` for the first turn and increment by one thereafter.
- `commands`:
  - Generate commands for one or more targets. 
  - Generate commads aligned with your current plan.
  - Each target (entry in the `command` list) will generate an unique image (composite image).
  - For each target, generate one or a sequence of camera movements. Each movement will be represented by a thumbnail-like image in a composite image.
  - For one target, prefer execute in the same sequence, instead of multiple entries.
- `rotatio_sequence`: 
  - Generate as one string, with the command separated by ',', and operation and value separated by ':'. Ex: "reset:y,yaw:30,yaw:30,yaw:30"
- `final_answer`: Lease this field as `null` during your investigation. Set a value only when you concluded your investigation and are sure or your answer. This will end the iteration process.

---

### **Think with Imagery**

**IMPORTANT** Think in imagery way, not purely in pure reasoning way. This means:

- Think grounded in images.
- Conduct the process in incremental investigative way. In each step, generate clear evidence image. Work in focused way. Don't generate too much, too broadly. Don't generate too much image in one iteration.
- Prefer longer investigative session, instead of too collapsed high density reasoning chain of thought.
- To understand the inner structure, helps generate longer sequence of the camera movement commands. 
- To conclusions, helps generate same angles views for the candidates.
- A clear final evidence should be a side by side comparision of the same angle view, between the solution candidate, and the original. Try to generate this final evidence before your final answer, as much as possible.
- Use reasoning to conduct the investigation and drill-down the candidates, but rely heavily on clear image evidence to make conclusions, partial of final.

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


class ToolsBackedImageryReasoner_Eval94:

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
