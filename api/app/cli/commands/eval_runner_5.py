import datetime
from bson import ObjectId

from app.cli.commands.helpers.command_base import CommandBase
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.services.chat_message_service import ChatMessageService
from pathlib import Path
import json

from app.services.chat_message_service_with_imagery_for_eval import (
    ChatMessageServiceWithImageryForEval,
)


def register(subparsers):
    parser = subparsers.add_parser("eval5")
    parser.add_argument("--start", required=False)
    parser.add_argument("--end", required=False)
    parser.set_defaults(handler=EvalRunner5)


class EvalRunner5(CommandBase):

    root_path = CommandBase.spatialviz_root_path / "problems/dataset-eval2-1001--3d-rotation-level-0"

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.runner = ChatMessageServiceWithImageryForEval()

    async def __call__(self):

        # read the problems
        with open(Path(self.root_path, "problems.json")) as f:
            problems = json.load(f)

        # read the foundation code template
        # with open(Path(self.root_path, "foundation_code_template.py")) as f:
        #     template_code = f.read()
        # print( "Template code: ", template_code)

        # read the bounds
        with open(Path(self.root_path, "foundation_bounds.json")) as f:
            bounds = json.load(f)
        bounds_map = {b["image_id"]: b["bounds"] for b in bounds}

        # create a folder under root_path, with the patter result_yyyymmdd_hhmmss
        eval_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = self.root_path / f"result_{eval_id}"
        result_dir.mkdir(parents=True, exist_ok=False)

        result = []
        # for each problem
        # {
        #     "Category": "MentalRotation",
        #     "Task": "3DRotation",
        #     "Level": "Level0",
        #     "Image_id": "1-2-3-1-4",
        #     "Question": "The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B, C, or D.",
        #     "Choices": [
        #         "A",
        #         "B",
        #         "C",
        #         "All three other options are incorrect"
        #     ],
        #     "Answer": "A",
        #     "Explanation": "{'A': 'Option A is correct because it was obtained by removing one small cube from the original stack.', 'C': 'Option C is incorrect because the cube stack can be obtained by rotating the original stack around the y-axis by 180 degrees.', 'B': 'Option B is incorrect because the cube stack can be obtained by rotating the original stack around the z-axis by 90 degrees.'}"
        # }
        score = 0
        start = int(self.args.start or "0")
        end = int(self.args.end or "99999")
        print(f"From {start} to {end}")
        for idx, problem in enumerate(problems[start:end]):
            print(f"\n\n{'*'*30} Problem {start+idx}/{end-1} {'*'*30}\n\n")
            # create the chat title for this problem
            problem_id = f"{problem['Category']}-{problem['Task']}-{problem['Level']}-{problem['Image_id']}"
            title = f"{eval_id}--{problem_id}"
            image_id = f"{problem['Image_id']}"

            bounds = [tuple(b) for b in bounds_map[image_id]]
            # image_code = template_code.replace('"BOUNDS_PLACEHOLDER"', str(bounds))

            foundation_model_image_url = (
                f"file://{Path(self.root_path, "foundation_model_image", image_id)}.png"
            )
            image_url = f"file://{Path(self.root_path, "images", image_id)}.png"
            # run eval

            # print( 'image_code: ', image_code)

            # answer = 'A'
            answer = await self.run_eval(
                title, problem, foundation_model_image_url, image_url, bounds
            )

            # store the result
            # compare with the correct result
            result.append(
                {
                    "problem_id": problem_id,
                    "title": title,
                    "answer": answer,
                    "correct": answer == problem["Answer"],
                }
            )
            if answer == problem["Answer"]:
                score += 1

        # print score
        print(f"Score: {score / len(result)}")
        # save score
        with open(result_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2)
        with open(result_dir / "score.json", "w") as f:
            json.dump({"score": score / len(result)}, f)

    async def run_eval(
        self, title, problem, foundation_model_image_url, image_url, bounds
    ):

        # create the chat message
        chat_message: ChatMessage = ChatMessage(
            chat_id=str(ObjectId()),
            project_id=self.project_id,
            title=title,
            message=f'Question: {problem["Question"]}\nChoices: {",".join(problem["Choices"])}',
            use_model=[ModelWithParameters(name="tools-based-imagery--eval-5")],
            preset_list=[
                {
                    "role": "user",
                    "content": None,
                    "file_url": image_url,
                    "file_name": problem["Image_id"] + ".png",
                    "content_type": "image/png",
                }
            ],
            imagery_args={
                "foundation_image_url": foundation_model_image_url,
                "bounds": bounds,
                "question_image_url": image_url,
                "question_file_name": problem["Image_id"] + ".png",
            },
        )
        answer = await self.runner.evaluate(chat_message)
        return answer
