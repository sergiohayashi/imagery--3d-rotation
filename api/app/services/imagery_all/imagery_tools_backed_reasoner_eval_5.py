import datetime
import json

from pathlib import Path

from openai import BaseModel
from app.llm_services.any_model import AnyModel
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.models.file_category import FileCategory
from app.services.imagery_all.stateful_imagery import StatefulImageryModule
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json


hints = """
** HINTS TO RESOLVE THE PROBLEM **
- Generate as much perspective images as necessary, to create a mental model of the underlyning structure.
- the problem structure are blocks stacked in some way.
- **important**: Remember that the concept of `height` or `horizontal`, `vertical`, `left`, `right` is relative, that depends on the camera angle. Don't rely on that in your reasoning. You need to figure out the blocks relative position, that is an **invariant** of the camera position.
- If, in you reasoning you are putting terms like `height`, `horizontal`, this is a indication that you are making wrong assumption.
- use features that don't change with rotation, like the number of boxes and the relative position.
- the resulting color or shades can differ depending on the rendering. Don't depend on that.
- use spatial information of the model, the relative position between the boxes. This is an invariant that don't change!
- what the question is asking is, `assuming that I have a 3D model block composed by a number of individual cubes of size 1 in all 3 directions, what camera view snapshot (that is given as a 2d image) don't correspont to that 3d model object`. Note that the object can not be reassembled or modified, just rotated (change of the camera angle) witch gives you a 2d image.
- To answer correctly, you need to figure out at least the number of cubes, and how they are assembled.
- **IMPORTANT**: Models has been incorrectly identifying the number of cubes. Double-check by generating clear perspectives. 
- The 3D models in this problem have all height of 1 in the z-axis (not stacked in this direction), which means, if you get a view from the top, you can see clearly all the cubes. 
- Remember, the images are a perspective view of a 3D model. So, some parts can be different facets of the same cube. 

""".strip()

reasoner_pre_answer = (
    """
This is a visual problem.

You are given a 2D perspective image of an underlyining 3D model, a question and some alternatives to select.

This is not just a problem to question in usual way. It is intended to be resolved in a iterative way.

In one call, you will execute one iteration of this process. In the history you will receive the context of the previous iteration.

The problem image itself is backed by an underlying 3D model. You don't have access to this model, but you will have a helper module called `imagery module` that knows about the 3D model, and can generate new perspective images result of one or more rotation command.

Analyze the question and the previous iteration result, and decide which rotation will help your the reasoning toward answer the original problem.

Generate the instruction in this format:

```json
{
  "rationale": "Explain here, for further reference as chain of throughts, your current conclusion from the last iteration request command result (2D image result of the rotation instruction), and the reasoning behind the next instruction. Also, write any partial conclusion.",
  "rotation_command": "Describe here the next rotation command"
}
```
The `rotation_command` is given by a comma separated sequence of commands.
Each command is defined by a mode and the degree. 
The possible commands are "yaw", "pitch" and "roll".
This is an example: "yaw:30,yaw:10,pitch:10,roll:10"
This example ask to a "yaw" operation in 30 degree, followed by another yaw by 10 degree, and so on.
Each command will generate an intermediary snapshot image as result. In this case, you will receive a image with 4 snapshots in it.
Ask for more than one snapshot at once, to have more context of the rotation. Recommended is more than 4.
As context, only the last 3 iteration's snapshot image will be provided.
Each image will be annotated by the command and the position.
This is an example of the label: "seq:1 command:[yaw:30],pos:[-2.7,8.8,-0.1]_az:0.0°_el:0.0°"

---

In the 'rationalile' comment include the sequential number. The first time you generate a rationale (which means, there is no previous rationale) in the context,
start with 1. After that, increment 1 to the last rationale.

---

** METHODOLOGY **
- Double check your conclusion before give the final answer, by generating clear evidence. For example, if you conclude that it is a 5 cube object, than generate image that evidence that. Remember, you can have intermediary wrong conclusion, so don't answer without get a clear evidence. Use word like `wait, ..` or `now, let me generate the evidence for my assumption...` to create confidence that you check all possibilities, without give your answer.



** IMPORTANT **
Generate your answer in **json** format as specified!

"""
    + hints
)

reasoner_with_answer = (
    """
This is a visual problem.

You are given a 2D perspective image of an underlyining 3D model, a question and some alternatives to select.

This is not just a problem to question in usual way. It is intended to be resolved in a iterative way.

In one call, you will execute one iteration of this process. In the history you will receive the context of the previous iteration.

The problem image itself is backed by an underlying 3D model. You don't have access to this model, but you will have a helper module called `imagery module` that knows about the 3D model, and can generate new perspective images result of one or more rotation command.

Analyze the question and the previous iteration result, and decide which rotation will help your the reasoning toward answer the original problem.

Generate the instruction in this format:

```json
{
  "final_answer": "the final answer in case you can answer the question with conviction",
  "rationale": "Explain here, for further reference as chain of throughts, your current conclusion from the last iteration request command result (2D image result of the rotation instruction), and the reasoning behind the next instruction. Also, write any partial conclusion.",
  "rotation_command": "Describe here the next rotation command"
}
```
The `rotation_command` is given by a comma separated sequence of commands.
Each command is defined by a mode and the degree. 
The possible commands are "yaw", "pitch" and "roll".
This is an example: "yaw:30,yaw:10,pitch:10,roll:10"
This example ask to a "yaw" operation in 30 degree, followed by another yaw by 10 degree, and so on.
Each command will generate an intermediary snapshot image as result. In this case, you will receive a image with 4 snapshots in it.
Each image will be annotated by the command and the position.
This is an example of the label: "seq:1 command:[yaw:30],pos:[-2.7,8.8,-0.1]_az:0.0°_el:0.0°"

---

In the 'rationalile' comment include the sequential number. The first time you generate a rationale (which means, there is no previous rationale) in the context,
start with 1. After that, increment 1 to the last rationale.

** IMPORTANT **
Generate your answer in **json** format as specified!
"""
    + hints
)


reasoner_for_final_answer = (
    """
For this visual problem, generate the answer in the following json format:
```json
{
  "final_answer": "Your answer to the visual problem",

}
```
"""
    + hints
)


class ResponseWithoutAnswer(BaseModel):
    rationale: str
    rotation_command: str


class ResponseWithAnswer(BaseModel):
    final_answer: str
    rationale: str
    rotation_command: str


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
    allowed_commands = {"yaw", "pitch", "roll"}
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
        try:
            float(value)
        except Exception:
            return True
    return False


class ToolsBackedImageryReasoner_Eval5:

    # REASONING_MODEL = 'chatgpt-4o-latest'
    REASONING_MODEL = "gpt-5"
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
        bounds = chat_message.imagery_args["bounds"]
        foundation_image_url = chat_message.imagery_args["foundation_image_url"]

        # create the stateful imagery model
        imagery = StatefulImageryModule(bounds, off_screen=True, show_grid=False)

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
                reasoner_system_message = reasoner_pre_answer
                response_schema = ResponseWithoutAnswer.model_json_schema()
            else:
                reasoner_system_message = reasoner_with_answer
                response_schema = ResponseWithAnswer.model_json_schema()

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
            final_answer = response_dict.get("final_answer")
            if final_answer:
                print('"final_answer" found. Finish')
                return final_answer, chat_history, None

            # if there is no instruction to imagery, finish
            rotation_command = response_dict.get("rotation_command")

            if not rotation_command or invalid(rotation_command):
                print("Invalid or no rotation_command found. Finish")
                return response, chat_history, None

            print("rotation command: ", rotation_command)

            # -- continues iteration --
            # build history for reasoning
            rationales.append({"role": "assistant", "content": response})

            # call imagery
            print(
                f"\n=================== Call IMAGERY {iter_count} {rotation_command} ==================\n"
            )
            image_path = imagery.run_sequence_and_save_image(rotation_command)
            print(f"image_path: [{image_path}]: <<")
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
            f"\n=================== Exceeded MAX. Reasoning model LAST call ==================\n"
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
