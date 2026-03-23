import asyncio
import datetime
import json
from pathlib import Path

from app.llm_services.any_model import AnyModel
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.models.file_category import FileCategory
from app.services.imagery.reason_with_imagery import MAX_ITERATION
from app.services.imagery.utils import extract_code_blocks
from app.services.imagery_with_tools.dynamic_render_service import run_with_exec
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json

reasoner_pre_answer = """
There is a visual problem.

As the problem statement, you are given a 2D perspective image, some answer alternatives and a question asking to select the correct alternative.

This problem will be resolved in a iterative way.

Your task is to execute one iteration of this process.

The problem image is backed by an underlying 3D model. You don´t have access to this model, but there is a helper module called imagery module that have access to it, and know exactly how to manipulate.

In one iteration, you will generate an instruction to this imagery module, to give you another perspective, towards the direction of result the problem.

Generate the instruction in this format:

```json
{
  "rationale": "Explain the reasoning behind why this visual instruction is useful toward understanding or evidencing the solution.",
  "instructions_to_imagery": "Describe the exact visual modification or manipulation to apply to the image."
}
```

The imagery module don't know the problem itself, nor the alternative blocks.
The imagery module knows the problem 3D model, and how to make small manipulation.
The imagery module, once received the instruction, will generate a new perspective image, that will be a helper toward resolve the problem. So, make this assumption when generating the instruction.
Don't ask to generate an image, it is implicit in the process. In the instruction only include image/model manipulation specific instruction.
Be as direct as possible in the instruction. Don't need to explain why. Put the 'why' in the 'rationale'.

""".strip()

reasoner_with_answer = """
There is a visual problem.

As the problem statement, you are given a 2D perspective image, some answer alternatives and a question asking to select the correct alternative.

This problem will be resolved in a iterative way.

Your task is to execute one iteration of this process.

The problem image is backed by an underlying 3D model. You don´t have access to this model, but there is a helper module called imagery module that have access to it, and know exactly how to manipulate.

In one iteration, you will generate an instruction to this imagery module, to give you another perspective, towards the direction of result the problem.

Generate the instruction in this format:

```json
{
  "final_answer": "the final answer in case you can answer the question with conviction",
  "rationale": "Explain the reasoning behind why this visual instruction is useful toward understanding or evidencing the solution.",
  "instructions_to_imagery": "Describe the exact visual modification or manipulation to apply to the image."
}
```

The imagery module don't know the problem itself, nor the alternative blocks.
The imagery module knows the problem 3D model, and how to make small manipulation.
The imagery module, once received the instruction, will generate a new perspective image, that will be a helper toward resolve the problem. So, make this assumption when generating the instruction.
Don't ask to generate an image, it is implicit in the process. In the instruction only include image/model manipulation specific instruction.
Be as direct as possible in the instruction. Don't need to explain why. Put the 'why' in the 'rationale'.
""".strip()


reasoner_for_final_answer = """
For this visual problem, generate the answer in the following json format:
```json
{
  "final_answer": "Your answer to the visual problem",

}
```
""".strip()


imagery_system_instruction = """
You are provided an initial 3D model generation code, that will be the 'foundation model', followed by the 2D image, generated from that.

Assume that there was a sequence of iteration to manipulate this 3D model, and generate 2D image in each step. These are small manipulation on the image, like rotation, change the camera angle, and in each step it has been generated the 2D image.

In you prompt, alongside the initial foundation, you will be provided the last manipulation code, and the resulting 2D image, in case that this is not the first iteration.

And, at last, you will be provided with a **new** instruction. 

You task is to generate the code in pyvista that implement this **last** instruction.

Generate the **full image drawing code**, not just the manipulation part, so that when executed will generate the desired image.                   
The output should be generated to a provided property called `OUTPUT_PATH`.

Here an example of the code:
```
import pyvista as pv

# IMPORTANT! Enable off-screen rendering (no window display)
pv.OFF_SCREEN = True

plotter = pv.Plotter(off_screen=True)    # IMPORTANT: off-screen
plotter.set_background("white")

cubes = [...]

for geom, color in cubes:
    plotter.add_mesh(geom, color=color, show_edges=True, edge_color="black")

plotter.reset_camera()
plotter.camera_position = [
    (1.0, 0.0, 10.0),
    (1.0, 0.0, 0.5),
    (0, 1, 0),
]
plotter.camera.zoom(0.5)
plotter.show_grid()

# IMPORTANT: write to OUTPUT_PATH.  Without this, the server raises an error.
# OUTPUT_PATH is an injected variable, just use as is.
plotter.show(screenshot=OUTPUT_PATH, auto_close=True)
```

Generate the code part between three backstick's.     

Caution with pyvista code:
- The pyvista method 'show_grid' is a wrapper to 'show_bounds'. So, the parameters  
'line_width', 'linestyle', 'tick_direction', 'axis', 'gridline_location' are invalid!
- camera zoom too large can not give the entire perspective. Try to use the original foundation model zoom value. 
 
""".strip()

# foundation_model_code = """
# ```python
# import pyvista as pv

# plotter = pv.Plotter(window_size=(800, 600))
# plotter.set_background("white")

# plotter.add_mesh(pv.Cube(bounds=(0, 1, 0, 1, 0, 1)), color="lightblue", show_edges=True)
# plotter.add_mesh(pv.Cube(bounds=(0, 1, 1, 2, 0, 1)), color="lightblue", show_edges=True)
# plotter.add_mesh(pv.Cube(bounds=(0, 1, 2, 3, 0, 1)), color="lightblue", show_edges=True)
# plotter.add_mesh(pv.Cube(bounds=(1, 2, 0, 1, 0, 1)), color="lightblue", show_edges=True)

# plotter.reset_camera()
# plotter.camera_position = [
#     (3, -2, 3),  # camera position
#     (0.5, 0.5, 0),  # focal point
#     (-0.5, 0.5, 0.5)   # view-up direction
# ]

# plotter.camera.zoom(0.5)
# """.strip()

# foundation_image_url = "https://simplechat-local.s3.us-east-1.amazonaws.com/pseudo-1-2aa1bc2b/68d0608a-559d3b75/u/mentalrotation3d12314_8f9bbfcf2581408ba00461eb0aaba8b7.png"

REASONING_MODEL = "chatgpt-4o-latest"
# REASONING_MODEL = 'gpt-5'   # effort = "low"
IMAGERY_MODEL = "gpt-5-mini"  # effort = default


class ToolsBackedImageryReasoner_Eval3:

    @staticmethod
    async def reason_loop(
        chat_message: ChatMessage,
        model: str | ModelWithParameters,
        options=None,
        save_raw=True,
    ):
        model_name = REASONING_MODEL

        async def call_llm(history, model_name, options):
            print(
                "\n------------------------->>>\ncall_llm:>>>",
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
            print(
                "\n-------------------------<<<\ncall_llm:<<<",
                json.dumps(_meta.get("output"), indent=2, cls=CustomJSONEncoder),
            )
            return _answer, _image_url, _files, _meta

        def get_now():
            nonlocal datetime_incrementer
            datetime_incrementer += 1000
            return (
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.datetime.resolution * datetime_incrementer
            )

        # -- main body --
        datetime_incrementer = 0
        chat_history = []
        if not chat_message.preset_list:
            raise Exception("Expected preset for imagery eval")

        c = chat_message.preset_list[0]
        chat_history.append(
            dict(
                role=c["role"],
                content=c["content"],
                id=None,
                image_url=c.get("image_url"),
                file_url=c.get("file_url"),
                file_name=c.get("file_name"),
                content_type=c.get("content_type"),
                created_at=get_now(),
                persist=True,
            )
        )

        chat_history.append(
            dict(
                role="user",
                content=chat_message.message,
                created_at=get_now(),
                id=None,
                persist=True,
            )
        )

        freeze_history = chat_history[
            :
        ]  # history holds the history for this interation only

        rationale_with_instruction_and_result_history = []  # only <rationale> entries
        imagery_history = []  # <ask to imagery> + resulting image sequence

        MAX_ITERATION = 5
        iter_count = 1
        iter_steps = []
        foundation_model_code = f"```python\n{c.get('foundation_model_code')}\n```"
        foundation_image_url = c.get("foundation_image_url")
        while iter_count <= MAX_ITERATION:

            # call reasoner module with imagery module aware prompt, and last image if exists
            print(
                f"\n=================== Call REASONING model {iter_count} ==================\n"
            )

            reasoner_system_message = (
                reasoner_pre_answer if iter_count <= 3 else reasoner_with_answer
            )
            response, _, _, _ = await call_llm(
                [{"role": "system", "content": reasoner_system_message}]
                + freeze_history
                + rationale_with_instruction_and_result_history,
                model_name,
                options,
            )

            # if models decide to finish, return
            response_dict = parser_json(response)
            final_answer = response_dict.get("final_answer")
            instructions_to_imagery = response_dict.get("instructions_to_imagery")
            if final_answer and not instructions_to_imagery:
                print('"final_answer" found and no instructions. Finish')
                return final_answer, chat_history, iter_steps

            # if there is no instruction to imagery, finish
            if not "instructions_to_imagery" in response_dict:
                print('No "instructions_to_imagery" found. Finish')
                return response, chat_history, iter_steps

            # -- continues iteration --
            # build history for reasoning
            rationale_with_instruction_and_result_history.append(
                {"role": "assistant", "content": response}
            )

            # history for imagery
            imagery_instruction = instructions_to_imagery

            MAX_RETRY = 3
            attempts = 1
            while True:
                print(
                    f"\n=================== Call IMAGERY model {iter_count} attempt: {attempts}/{MAX_RETRY}==================\n"
                )
                try:
                    response, image_url, files, meta = await call_llm(
                        [
                            {  # system message
                                "role": "system",
                                "content": imagery_system_instruction,
                            },
                            {"role": "system", "content": "# foundation model"},
                            {"role": "system", "content": foundation_model_code},
                            {"role": "system", "image_url": foundation_image_url},
                        ]
                        + imagery_history[-3:]
                        + [
                            {"role": "user", "content": f"{imagery_instruction}"}
                        ],  # previous instruction->previous generate image -> last instruction
                        IMAGERY_MODEL,
                        None,
                        # {
                        #     "use_image_generation": True,
                        #     "use_image_generation__options": {
                        #         "quality": "low"
                        #     }
                        # },
                    )

                    # extract the code part
                    code = extract_code_blocks(response)
                    if not code:
                        raise Exception(f"Code not generated. response = {response}")
                    print(f"code: [{code}]: >>")

                    # execute the code and extract the image
                    image_path = run_with_exec(code)
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
                                    content="[image generated by code interpreter]",
                                    image_url=image_url,
                                    persist=True,
                                )
                            )

                        break  # done!
                    else:
                        raise Exception(f"Image not generated {response}")
                except Exception as e:
                    print(f"Error: {e}")
                    if attempts < MAX_RETRY:
                        print(
                            f"\n*** Image not generated in attempts {attempts}/{MAX_RETRY}! Sleep {2**attempts} seconds and retry"
                        )
                        await asyncio.sleep(2**attempts)
                    else:
                        raise  # give-up
                attempts += 1

            # imagery history
            rationale_with_instruction_and_result_history.append(
                {"role": "assistant", "image_url": image_url}
            )

            # imagery history
            imagery_history.extend(
                [
                    {"role": "user", "content": imagery_instruction},
                    {"role": "assistant", "content": f"```pyton\n{code}\n```"},
                    {"role": "assistant", "image_url": image_url},
                ]
            )

            iter_count += 1

        # exceed iterations, call without system message
        print(f"\n=================== Call reasoning model PLAIN ==================\n")
        response, _, _, _ = await call_llm(
            [{"role": "system", "content": reasoner_for_final_answer}]
            + freeze_history
            + rationale_with_instruction_and_result_history,
            model_name,
            options,
        )

        response_dict = parser_json(response)
        return response_dict.get("final_answer", response), chat_history, iter_steps
