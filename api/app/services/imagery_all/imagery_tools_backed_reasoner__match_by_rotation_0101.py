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
# TASK AND ITERATIVE PROCESS

You are given a Target View B and a Current View A of the same object. 
Use the imagery module commands (left, right, up, down, etc.) to rotate the Current View A until it exactly matches the Target View B.

# IMAGERY MODULE
To solve this problem, you will work together with a tool called the imagery module.

The imagery module holds a 3D representation of the problem object and performs rotation operations on your behalf, and generates snapshots (images) corresponding to the current state (i.e., camera angle). The state of the object is maintained throughout the entire process. 

Working with the imagery module is an iterative process, controlled externally. It works in TURNS between you and the imagery module. On your turn, analyze the previous result and and generate rotation commands to the imagery module. Then, the imagery module, on its turn, will apply these rotations and return the snapshot images of the objects in the new state. Then it is your turn again, and so on.

Rotation commands are defined in camera space (relative to the current view centered in the object) simulating the inverse of camera movement. Intuitively, this matches the view of manipulating an object in your hands: the object spins around its center while the camera (your viewpoint) remains fixed. 

Possible commands are:
- `left:value` (object is rotated to left)
- `right:value` (object is rotated to right)
- `up:value` (object is rotated up)
- `down:value` (object is rotated down)
- `rotate:cw:value` (object rotates clockwise in the image plane)
- `rotate:ccw:value` (object rotates counterclockwise in the image plane)

`value` refers to the rotation angle in degrees. Angle 0 is also valid and can be used to get a snapshot of the current state.

# OUTPUT
Return your response in JSON format, following the format below:
```json
{
  "rationale": "Your rationale",
  "iteration_number": 1,
  "rotation_commands": "right:15,right:15,up:10"
  "done": true/false
}
```

Details of the output fields:
- `rationale`: You rationale of the situation.
- `commands`: Rotation instructions for the imagery module. You can generate for one or more targets. Rotation sequence can have one or more commands, separated by comma. Each command generates a snapshot image of the after-rotation view, and will be combined in a grid image, per target, having the effect of a sequence showing the object rotating incrementally. 
- `iteration_number`: Iteration counter. Start with 1 and increment this number each turn. Max iteration is 12.
- `done`: Set `true` when you finished the rotation. Empty list of commands will be interpreted as finished also.

Enclose the JSON object in ```json and ```.

*IMPORTANT*
In each turn, generate exactly one JSON output and FINISH. DON'T simulate the iteration or the imagery module turn. It is handled externally.

# CONVERSATION CONTEXT
The conversation context, in each turn, will contain the following content:
- The problem statement with the target view B, 
- All the previous output with rationale and rotation commands.
- The images sequence of the last command, that represent also the current object view state..

# RULES
You have a maximum of 12 turns.

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

    rationale_with_imagery_response = []
    for i in range(len(rationales)):
        rationale_with_imagery_response.append(rationales[i])
        # for image, include only the last 3 images
        if i >= len(imagery_images) - 1:
            for image_url, content in imagery_images[i]:
                rationale_with_imagery_response.append(
                    dict(
                        # role="assistant",
                        role="user",  # gpt 5.2 not support assistant role for image content
                        content=content,
                        image_url=image_url,
                    )
                )
    return rationale_with_imagery_response


# def rationale_with_imagery_response_last_3_only(rationales, imagery_images):
#     """
#     This version pass throuth only the last 3 iterarations
#     """
#     # ensure that rationale and imagery response are in the same length
#     assert len(rationales) == len(
#         imagery_images
#     ), "Rationale and imagery response must be in the same length"

#     rationales = rationales[-2:]
#     imagery_images = imagery_images[-2:]

#     rationale_with_imagery_resonse = []
#     for i in range(len(rationales)):
#         rationale_with_imagery_resonse.append(rationales[i])
#         # if i >= len(imagery_images) - 1:   #include only the last 1 iteration image
#         for image_url, content in imagery_images[i]:
#             rationale_with_imagery_resonse.append(
#                 dict(
#                     # role="assistant",
#                     role="user",  # gpt 5.2 not support assistant role for image content
#                     content=content,
#                     image_url=image_url,
#                 )
#             )
#     return rationale_with_imagery_resonse


# def invalid(cmd_string):
#     # Valid command format: "yaw:10,pitch:30,roll:-10"
#     allowed_commands = {"left", "right", "up", "down", "rotate"}
#     if not isinstance(cmd_string, str):
#         return True
#     cmds = [cmd.strip() for cmd in cmd_string.split(",") if cmd.strip()]
#     if not cmds:
#         return True
#     for cmd in cmds:
#         if ":" not in cmd:
#             return True
#         command, value = cmd.split(":", 1)
#         if command.strip().lower() not in allowed_commands:
#             return True
#         # if command != "reset":
#         #     try:
#         #         float(value)
#         #     except Exception:
#         #         traceback.print_exc()
#         #         return True
#         # else:
#         #     if value not in ["x", "y", "z", "iso"]:
#         #         return True
#     return False


class ToolsBaseImageryMatchByRotation00101:

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
            # print(
            #     f"\n------------------------->>>\ncall_llm {model_name}:>>>",
            #     json.dumps(history, indent=2, cls=CustomJSONEncoder),
            # )
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


        async def call_imagery_module(target, commands):
            # join same target commands
            # target = "A"
            # commands = "left:0,"+ commands    # include the current state command
            print(
                f"\n==[{cls.__name__}]================= Call IMAGERY {target} {commands} ==================\n"
            )
            image_path = imagery.run_human_sequence_and_save_image(
                target, commands, image_title="Current View"
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
                return image_url, content
            else:
                return None, None


        # --- main body ---
        datetime_incrementer = 0
        bounds_map = chat_message.imagery_args["bounds_map"]
        # foundation_image_url = chat_message.imagery_args['foundation_image_url']

        alt = chat_message.imagery_args.get('alt')
        bounds_map = {
            "A": bounds_map['original'],
            'B': bounds_map[alt],
        }
        # bounds_map = {k:v for k,v in bounds_map.items() if k in ['original', alt]}        

        # create the stateful imagery model
        imagery = StatefulImageryWithInitialRotationModule_8(
            bounds_map, off_screen=True, show_grid=False
        )

        # the first time only, include the inital state image of the object A



        try:
            # question image and question
            chat_history = [
                dict(
                    role="user",
                    file_url=chat_message.imagery_args["alt_image_url"],
                    file_name="Target View B",
                    content_type="image/png",
                    created_at=get_now(),
                    id=None,
                    persist=True,
                ),
                dict(
                    role="user",
                    content="Rotate the current object to match the target object view B.",
                    created_at=get_now(),
                    id=None,
                    persist=True,
                ),
                # dict(
                #     role="user",
                #     file_url=chat_message.imagery_args["original_image_url"],
                #     file_name="A",
                #     content_type="image/png",
                #     created_at=get_now(),
                #     id=None,
                #     persist=True,
                # ),
            ]

            freeze_history = chat_history[
                :
            ]  # history holds the history for this interation only

            MAX_ITERATION = 12+2
            iter_count = 1

            rationales = []
            imagery_images = []

            # the first time only, include the inital state image of the object A
            target = "A"
            image_url, content = await call_imagery_module(target, "left:0")
            if image_url:
                imagery_images.append([(image_url, "initial state of the object A")])
                rationales.append({"role": "assistant", "content": None})

            else:
                raise Exception(f"Image not generated {commands}")


            while iter_count <= MAX_ITERATION:

                # call reasoner module with imagery module aware prompt, and last image if exists
                print(
                    f"\n=================== Call REASONING model {iter_count} ==================\n"
                )

                # if iter_count <= MIN_ITERATION:
                #     reasoner_system_message = reasoner_with_answer
                #     response_schema = ResponseWithoutAnswer.model_json_schema()
                # else:
                # reasoner_system_message = prompt
                # response_schema = ResponseWithAnswer.model_json_schema()

                reasoning_retry_cout = 5
                valid = False
                while reasoning_retry_cout > 0:
                    reasoning_retry_cout -= 1
                    response, _, _, _ = await call_llm(
                        [{"role": "system", "content": prompt}]
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

                    commands = response_dict.get("rotation_commands")
                    is_done = response_dict.get( 'done') or not commands
                    if is_done:
                        return "None", chat_history, None

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
                # target = "A"
                # # commands = "left:0,"+ commands    # include the current state command
                # print(
                #     f"\n==[{cls.__name__}]================= Call IMAGERY {target} {commands} ==================\n"
                # )
                # image_path = imagery.run_human_sequence_and_save_image(
                #     target, commands, label="Object"
                # )
                # print(f"==[{cls.__name__}] image_path: [{image_path}]: <<")
                # if image_path:  # OK

                #     # read image bytes
                #     with open(image_path, "rb") as f:
                #         file_content = f.read()

                #     # upload to S3
                #     image_url = await S3UploadServices.upload_generate_image(
                #         Path(image_path).name,
                #         file_content,
                #         Path(image_path).suffix.lstrip("."),
                #         FileCategory.GENERATED,
                #     )
                #     print(f"image_url: [{image_url}]: <<")
                #     if not image_url:
                #         raise Exception(f"Error uploading file to S3 {image_path}")
                #     else:
                #         # await wait for 10 seconds
                #         await asyncio.sleep(10)

                #     content = f"[image generated by Imagery Module {imagery.__class__.__name__}] for target {target} and rotation sequence {commands}"
                #     if save_raw:
                #         chat_history.append(
                #             dict(
                #                 role="user",
                #                 content=content,
                #                 image_url=image_url,
                #                 created_at=get_now(),
                #                 persist=True,
                #             )
                #         )

                #     imagery_images.append([(image_url, content)])

                # else:
                #     raise Exception(f"Image not generated {response}")

                target = "A"
                image_url, content = await call_imagery_module(target, commands)
                if image_url:
                    imagery_images.append([(image_url, f"last command sequence snapshot with the current state of the object {target}")])
                else:
                    raise Exception(f"Image not generated {commands}")

                # # imagery history
                # imagery_images.append(command_images)

                iter_count += 1

            # exceed iterations, call without system message
            # print(
            #     f"\n=={cls.__name__}================= Exceeded MAX. Reasoning model LAST call ==================\n"
            # )
            # response, _, _, _ = await call_llm(
            #     [{"role": "system", "content": reasoner_for_final_answer}]
            #     + freeze_history
            #     + rationale_with_imagery_response(rationales, imagery_images),
            #     cls.REASONING_MODEL,
            #     options,
            # )

            # response_dict = parser_json(response)
            return None, chat_history, None

        finally:
            imagery.close()
