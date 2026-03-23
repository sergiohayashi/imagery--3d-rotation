import asyncio
import json
import re
from pathlib import Path

from app.llm_services.any_model import AnyModel
from app.models.chat_message import ModelWithParameters
from app.models.file_category import FileCategory
from app.services.imagery_with_tools.dynamic_render_service import run_with_exec
from app.services.s3_services import S3UploadServices
from app.utils.file_utils import CustomJSONEncoder
from app.utils.json_utils import parser_json
from app.utils.prompt_loader import get_prompt

MAX_ITERATION = 3

# imagery_model = "gpt-5-nano"
# imagery_model = "gpt-5-nano"
# imagery_model = "gpt-4.1"
# REASONING_MODEL = 'chatgpt-4o-latest'
# REASONING_MODEL = 'gpt-5-nano'
# REASONING_MODEL = 'gemini-2.5-flash-lite'
# REASONING_MODEL = 'gpt-5-nano'
# IMAGERY_MODEL = 'gemini-2.5-flash-lite'
# IMAGERY_MODEL = 'gemini-2.5-flash-lite'

# Esse par funciona bem!
# REASONING_MODEL = 'gpt-5'   # effort = "low"
# IMAGERY_MODEL = 'gpt-5-mini'    # effort = default

# Não funciona. Alucinate, e gera um texto bem grande..
# REASONING_MODEL = 'gemini-2.5-flash-lite'   # effort = "low"
# IMAGERY_MODEL = 'gemini-2.5-flash-lite'    # effort = default

# gera um texto grande, e não é estável
# REASONING_MODEL = 'gemini-2.5-flash'   # effort = "low"
# IMAGERY_MODEL = 'gemini-2.5-flash'    # effort = default

REASONING_MODEL = "gpt-5"  # effort = "low"
IMAGERY_MODEL = "gpt-5-mini"  # effort = default


reasoner_system_message = """
# Task

You are going to be asked a visual question.

To solve this question, you will work together with an imagery module.

The imagery module maintains the spatial representation (similar to a 3D model) of the problem and understands instructions. You can ask it to make small adjustments to the structure’s camera view and receive a new image showing a different perspective of that structure.

You will use this tool to help you answer the question.

In each iteration, generate instructions for the imagery module and review the resulting image.

Continue this process until you reach your final conclusion and produce the final answer.

Even if you can answer immediately, have the imagery module generate an image that serves as evidence of your answer before producing the final result. Repeat the process a number of times until have clear understanding of the structure and be convinced that the answer is correct.

Repeat at least 3 different views.

# Format

Generate the response in JSON format, as shown below:

```json
{
    "final_answer": "<the final answer>",
    "rationale": "<This is your memory across iterations. Record your findings here.>",
    "instructions_to_imagery": "<your next instruction to the imagery module>"
}
```

Include the final_answer field only when you are ready to conclude the iteration and present the final answer. Otherwise, you can omit it or leave it blank.

Always include the rationale field. This field will be passed back to you in the next iteration.

Include instructions_to_imagery when you want to make the next request to the imagery module.

# Guidelines for Requests to the Imagery Module

- The imagery module interprets text instructions but works only with spatial structures and image generation. This means it does not need to understand the question itself or assist directly in reasoning about the answer.

- The imagery module operates incrementally — instruct it to make small, progressive modifications. For example, more more to the right, zoom in. So, it is small movement around the structure.

- Give clear and direct image manipulation instructions, such as:
“Move the camera angle to the right,” “zoom in,” or “focus on a specific part of the structure.”


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
plotter.camera.zoom(1.2)
plotter.show_grid()

# IMPORTANT: write to OUTPUT_PATH.  Without this, the server raises an error.
# OUTPUT_PATH is an injected variable, just use as is.
plotter.show(screenshot=OUTPUT_PATH, auto_close=True)
```

Generate the code part between three backstick's.     

Caution with pyvista code:
- The pyvista method 'show_grid' is a wrapper to 'show_bounds'. So, the parameters  
'line_width', 'linestyle', 'tick_direction', 'axis', 'gridline_location' are invalid!
 
""".strip()


foundation_model_code = """
```python
import pyvista as pv

plotter = pv.Plotter(window_size=(800, 600))
plotter.set_background("white")

plotter.add_mesh(pv.Cube(bounds=(0, 1, 0, 1, 0, 1)), color="lightblue", show_edges=True)
plotter.add_mesh(pv.Cube(bounds=(0, 1, 1, 2, 0, 1)), color="lightblue", show_edges=True)
plotter.add_mesh(pv.Cube(bounds=(0, 1, 2, 3, 0, 1)), color="lightblue", show_edges=True)
plotter.add_mesh(pv.Cube(bounds=(1, 2, 0, 1, 0, 1)), color="lightblue", show_edges=True)

plotter.reset_camera()
plotter.camera_position = [
    (3, -2, 3),  # camera position
    (0.5, 0.5, 0),  # focal point
    (-0.5, 0.5, 0.5)   # view-up direction
]

plotter.camera.zoom(0.5)
""".strip()

foundation_image_url = "https://simplechat-local.s3.us-east-1.amazonaws.com/pseudo-1-2aa1bc2b/68d0608a-559d3b75/u/mentalrotation3d12314_178306fad9a143018d23bdf1146949e8.png"


def extract_code_blocks(text: str):
    """
    Extracts code blocks delimited by triple backticks (```),
    optionally followed by a language name.

    Returns a list of code strings.
    """
    pattern = r"```(?:\w+)?\n(.*?)```"
    return "".join(re.findall(pattern, text, re.DOTALL))


class ToolsBackedImageryReasoner_MentalRotation1:

    @staticmethod
    async def reason_loop(
        chat_history, model: str | ModelWithParameters, options=None, save_raw=True
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
            print(
                "\n-------------------------<<<\ncall_llm:<<<",
                json.dumps(
                    _meta if isinstance(_meta, dict) else _meta.model_dump(),
                    indent=2,
                    cls=CustomJSONEncoder,
                ),
            )
            return _answer, _image_url, _files, _meta

        # reasoner_system_message = get_prompt(Path(__file__).resolve().parent, "prompt-for-reasoning-module.txt")
        # imagery_system_message = get_prompt(Path(__file__).resolve().parent, "prompt-for-imagery-module.txt")

        freeze_history = chat_history[
            :
        ]  # history holds the history for this interation only

        rationale_history = []  # only <rationale> entries
        imagery_to_reasoning_response = []  # imagery last generated image entry
        imagery_history = []  # <ask to imagery> + resulting image sequence

        iter_count = 0
        iter_steps = []
        while iter_count < MAX_ITERATION:
            iter_count += 1

            # call reasoner module with imagery module aware prompt, and last image if exists
            print(
                f"\n=================== Call reasoning model {iter_count} ==================\n"
            )

            response, _, _, _ = await call_llm(
                [{"role": "system", "content": reasoner_system_message}]
                + freeze_history
                + rationale_history
                + imagery_to_reasoning_response,
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

            if "rationale" in response_dict:
                rationale_history.append(
                    {
                        "role": "assistant",
                        "content": f"rationale: {response_dict['rationale']}",
                    }
                )

            # history for imagery
            imagery_instruction = instructions_to_imagery

            MAX_RETRY = 3
            attempts = 0
            while True:
                attempts += 1
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

            # imagery history
            imagery_to_reasoning_response = [
                {
                    "role": "assistant",
                    "content": f"instructions_to_imagery: {imagery_instruction}",
                },
                {"role": "assistant", "image_url": image_url},
            ]

            # imagery history
            imagery_history.extend(
                [
                    {"role": "user", "content": imagery_instruction},
                    {"role": "assistant", "content": f"```pyton\n{code}\n```"},
                    {"role": "assistant", "image_url": image_url},
                ]
            )

        # exceed iterations, call without system message
        print(f"\n=================== Call reasoning model PLAIN ==================\n")
        answer, _, _, _ = await call_llm(
            freeze_history + rationale_history + imagery_to_reasoning_response,
            model_name,
            options,
        )

        return answer, chat_history, iter_steps
