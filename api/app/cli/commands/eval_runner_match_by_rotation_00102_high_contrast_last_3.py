import datetime
import logging
from bson import ObjectId

from app.cli.commands.helpers.command_base import CommandBase
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.services.chat_message_service import ChatMessageService
from pathlib import Path
import json

from app.services.chat_message_service_with_imagery_for_eval import (
    ChatMessageServiceWithImageryForEval,
)
from app.services.chat_message_service_with_imagery_for_eval_2 import (
    ChatMessageServiceWithImageryForEval2,
)
from app.services.chat_message_service_with_imagery_for_match_rotate import ChatMessageServiceWithImageryForMatchRotate


def register(subparsers):
    parser = subparsers.add_parser("match102")
    parser.add_argument("--start", required=False)
    parser.add_argument("--end", required=False)
    parser.add_argument("--list", required=False)
    parser.set_defaults(handler=EvalRunnerMatchByRotation00102)


class EvalRunnerMatchByRotation00102(CommandBase):

    data_root_path = CommandBase.data_root_path

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.runner = ChatMessageServiceWithImageryForMatchRotate()

    async def __call__(self):

        # read the problems
        with open(Path(self.data_root_path, "spatialviz/problems", "problems.json")) as f:
            problems = json.load(f)

        # read the bounds
        with open(
            Path(
                self.data_root_path,
                "spatialviz/problems",
                "foundation_bounds--with-alt-and-rotation-v1.json",
            )
        ) as f:
            problem_bouds_map = json.load(f)

        eval_id = (
            "match_rotation-high-contrast-last-3-"
            + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            + "_"
            + self.__class__.__name__
        )
        result_dir = self.data_root_path / "spatialviz/results" / f"result_{eval_id}"
        result_dir.mkdir(parents=True, exist_ok=False)


        if self.args.list:
            indexes = [int(i) for i in self.args.list.split(",")]
            problems_to_eval = [problems[i] for i in indexes if i < len(problems)]
        else:
            start = int(self.args.start or "0")
            end = int(self.args.end) if self.args.end else len(problems)
            problems_to_eval = problems[start:end]
        for idx, problem in enumerate(problems_to_eval):

            for alt in ['A', 'B', 'C']:
                if alt == problem["Answer"]:
                    continue

                logging.info(f"\n{'*'*30} Problem {problem['Image_id']} {alt} {'*'*30}\n")

                # create the chat title for this problem
                problem_id = f"{problem['Category']}-{problem['Task']}-{problem['Level']}-{problem['Image_id']}-{alt}"
                title = f"{eval_id}--{problem_id}"
                image_id = f"{problem['Image_id']}"

                # foundation_model_image_url = f"file://{Path(self.root_path, "problems", "foundation_model_image", image_id)}.png"
                original_image_url = (
                    f"file://{Path(self.data_root_path, "spatialviz-3d-slices/data", image_id)}_original.png"
                )
                alt_image_url = (
                    f"file://{Path(self.data_root_path, "spatialviz-3d-slices/data", image_id)}_{alt}.png"
                )

                try:
                    answer = await self.run_eval(
                        title,
                        problem,
                        # foundation_model_image_url,
                        original_image_url,
                        alt_image_url,
                        alt,
                        problem_bouds_map[image_id],
                    )


                except Exception as e:
                    logging.exception(f"Error in EvalRunner90.run_eval: {e}")


    async def run_eval(
        self, title, problem, original_image_url, alt_image_url, alt, problem_bouds_map
    ):

        question = "The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C."

        # create the chat message
        chat_message: ChatMessage = ChatMessage(
            chat_id=str(ObjectId()),
            project_id=self.project_id,
            title=title,
            message=f"Question: {question}",
            use_model=[
                ModelWithParameters(name="tools-based-imagery--match-by-rotation-00102")
            ],
            imagery_args={
                "bounds_map": problem_bouds_map,
                "original_image_url": original_image_url,
                "alt_image_url": alt_image_url,
                "alt": alt,
            },
        )
        answer = await self.runner.evaluate(chat_message)
        return answer

