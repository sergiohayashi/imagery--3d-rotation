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
from app.services.imagery_all.stateful_imagery_8_with_initial_rotation import (
    StatefulImageryWithInitialRotationModule_8,
)
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder

logger = logging.getLogger(__name__)


# "A": "unknown"|"matched"|"probably_not_match"



prompt = """
You are given an object (called **current**) and a **target** object.

The task is to rotate the current object to match the view of the target object.

To do this, you will use a tool.

The tool holds the 3D representation of the current object and can execute rotation commands and generate snapshots of the current view.

Your task is to interact with the tool by generating rotation commands until the current view matches the target view.

This is an iterative process controlled externally.

In each turn:
- analyze the current state,
- generate the next single rotation command,
- and stop.

In the next turn, the updated current object view will be provided.

Rotation commands are defined in camera space, relative to the current view. The view is always centered on the object and maintains a fixed distance from the center. The commands are defined as the inverse of camera movement. For example, the command `'right'` is equivalent to moving the camera to the left.

The possible commands are:

- left
- right
- up
- down
- clockwise
- counterclockwise

Each command rotates the object by a fixed angle of 30 degrees.

For each turn, your output must be:

- the rotation command,
- or `'STOP'` when the views match.

You will be provided with the current iteration number. The maximum number of iterations is 10.

In the context for each turn, you will receive:

- the last 3 command names and their results,
- where the last result represents the current state.


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
    if len(rationales)> 3:
        rationales = rationales[-3:]
        imagery_images = imagery_images[-3:]
    for rationale, imagery_image in zip(rationales, imagery_images):
        rationale_with_imagery_response.append(rationale)
        for image_url, content in imagery_image:
            rationale_with_imagery_response.append(
                dict(
                    role="user",  # gpt 5.2 not support assistant role for image content
                    content=content,
                    image_url=image_url,
                )
            )   
    return rationale_with_imagery_response


class ToolsBaseImageryMatchByRotation00102:

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

        async def call_llm(history, model_name, options = {}):
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


        async def call_imagery_module(target, commands, label):
            # join same target commands
            # target = "A"
            # commands = "left:0,"+ commands    # include the current state command
            print(
                f"\n==[{cls.__name__}]================= Call IMAGERY {target} {commands} ==================\n"
            )
            image_path = imagery.run_human_sequence_and_save_image(
                target, commands, image_title=label
            )
            print(f"==[{cls.__name__}] image_path: [{image_path}]: <<")
            if not image_path:
                raise Exception(f"Image not generated {commands}")


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

            # content = f"[image generated by Imagery Module {imagery.__class__.__name__}] for target {target} and rotation sequence {commands}"
            # if save_raw:
            return image_url


        def response_to_commands(response):
            if response == "clockwise":
                return "rotate:cw"
            elif response == "counterclockwise":
                return "rotate:ccw"
            else:
                return response 


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
            bounds_map, off_screen=True, show_grid=False, high_contrast=True
        )

        # the first time only, include the inital state image of the object A

        image_url = await call_imagery_module("B", "left:0", "Target")
        # if image_url:
        #     imagery_images.append([(image_url, "initial state of the object A")])
        #     rationales.append({"role": "assistant", "content": None})


        try:
            # question image and question
            chat_history = [
                dict(
                    role="user",
                    file_url=image_url,
                    file_name="Target",
                    content_type="image/png",
                    created_at=get_now(),
                    id=None,
                    persist=True,
                ),
                dict(
                    role="user",
                    content="Rotate the current object to match the Target object view",
                    created_at=get_now(),
                    id=None,
                    persist=True,
                ),
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
            image_url = await call_imagery_module(target, "left:0", "Current")
            imagery_images.append([(image_url, "initial state of the object A")])
            rationales.append({"role": "assistant", "content": None})
            chat_history.append(
                dict(
                    role="user",
                    content="",
                    image_url=image_url,
                    created_at=get_now(),
                    persist=True,
                )
            )

            while iter_count <= MAX_ITERATION:

                # call reasoner module with imagery module aware prompt, and last image if exists
                print(
                    f"\n=================== Call REASONING model {iter_count} ==================\n"
                )

                reasoning_retry_cout = 5
                valid = False
                while reasoning_retry_cout > 0:
                    reasoning_retry_cout -= 1
                    response, _, _, _ = await call_llm(
                        [{"role": "system", "content": prompt}]
                        + freeze_history
                        + rationale_with_imagery_response(rationales, imagery_images),
                        model_name,
                        # options = {}
                        # options={
                        #     "response_mime_type": "application/json",
                        # },
                    )

                    # response_dict = parser_json(response)
                    # if not isinstance(response_dict, dict):
                    #     print(f"Not a dictionary. RETRY {reasoning_retry_cout}")
                    #     continue

                    # commands = response_dict.get("rotation_commands")
                    # is_done = response_dict.get( 'done') or not commands
                    # if is_done:
                    #     return "None", chat_history, None
                    if response == "STOP":
                        return "None", chat_history, None

                    commands = response_to_commands(response)+":30"

                    # no final answer, valid rotation sequence. Valid output!
                    valid = True
                    break

                if not valid:
                    # handle as the model has answered 'None', and finish
                    return "None", chat_history, None

                # -- continues iteration --
                # build history for reasoning
                rationales.append({"role": "assistant", "content": response})

                # target = "A"
                image_url = await call_imagery_module(target, commands, "Current")
                chat_history.append(
                    dict(
                        role="user",
                        content="",
                        image_url=image_url,
                        created_at=get_now(),
                        persist=True,
                    )
                )
                imagery_images.append([(image_url, f"current object after the rotate to {response}")])
                iter_count += 1

            # response_dict = parser_json(response)
            return None, chat_history, None

        finally:
            imagery.close()
