import json
import logging
from pathlib import Path
import datetime

from bson import ObjectId
from app.cli.commands.helpers.command_base import CommandBase
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.services.chat_message_service_model_only_for_eval import (
    ChatMessageServiceModelOnlyForEval,
)


def register(subparsers):
    parser = subparsers.add_parser("model_9")
    parser.add_argument("--start", required=False)
    parser.add_argument("--end", required=False)
    parser.add_argument("--model", required=False)
    parser.add_argument("--list", required=False)
    parser.set_defaults(handler=EvalRunnerWithModel9)


class EvalRunnerWithModel9(CommandBase):

    root_path = CommandBase.spatialviz_root_path / "problems/dataset-eval2-1001--3d-rotation-level-0"

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.model = args.model
        self.runner = ChatMessageServiceModelOnlyForEval()

    async def __call__(self):

        # read the problems
        with open(Path(self.root_path, "problems.json")) as f:
            problems = json.load(f)

        # create a folder under root_path, with the patter result_yyyymmdd_hhmmss
        eval_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = self.root_path / f"result_{self.model}_{eval_id}"
        result_dir.mkdir(parents=True, exist_ok=False)

        result = []
        score = 0
        if self.args.list:
            indexes = [int(i) for i in self.args.list.split(",")]
            problems_to_eval = [problems[i] for i in indexes if i < len(problems)]
        else:
            start = int(self.args.start or "0")
            end = int(self.args.end) if self.args.end else len(problems)
            problems_to_eval = problems[start:end]
        for idx, problem in enumerate(problems_to_eval):
            logging.info(f"\n{'*'*30} Problem {problem['Image_id']} {'*'*30}\n")

            # create the chat title for this problem
            problem_id = f"{problem['Category']}-{problem['Task']}-{problem['Level']}-{problem['Image_id']}"
            title = f"{eval_id}--{problem_id}"
            image_id = f"{problem['Image_id']}"

            image_url = f"file://{Path(self.root_path, "images", image_id)}.png"

            # answer = 'A'
            try:
                answer = await self.run_eval(
                    title,
                    problem,
                    # foundation_model_image_url,
                    image_url,
                    # bouds_map_for_alternatives
                )

                # print if the answer is correct or wrong, using emoji
                print(
                    f"{'✅' if answer == problem['Answer'] else '❌'} {'Correct' if answer == problem['Answer'] else 'Wrong'} answer: {answer} (Expected: {problem['Answer']})"
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
            except Exception as e:
                logging.exception(f"Error in EvalRunner8.run_eval: {e}")
                result.append(
                    {
                        "problem_id": problem_id,
                        "title": title,
                        "answer": "ERROR",
                        "correct": False,
                        "error": str(e),
                    }
                )

            print(f"Current Score: {score / (idx+1)}")
            # store current result and score
            with open(result_dir / f"result_{idx}.json", "w") as f:
                json.dump(result, f, indent=2)
            with open(result_dir / f"score_{idx}.json", "w") as f:
                json.dump({"score": score / len(result)}, f)

        # print score
        if result:
            print(f"Score: {score / len(result)}")
            # save score
            with open(result_dir / "result.json", "w") as f:
                json.dump(result, f, indent=2)
            with open(result_dir / "score.json", "w") as f:
                json.dump({"score": score / len(result)}, f)
        else:
            print("No result")

    async def run_eval(
        self,
        title,
        problem,
        # foundation_model_image_url,
        image_url,
        # bounds_map
    ):

        question = "The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C."

        # create the chat message
        chat_message: ChatMessage = ChatMessage(
            chat_id=str(ObjectId()),
            project_id=self.project_id,
            title=title,
            message=f"Question: {question}",
            # message=f'Question: {problem["Question"]}\nChoices: {",".join(problem["Choices"])}',
            use_model=[ModelWithParameters(name="gpt-5.2")],
            # preset_list=[{
            #     "role": "user",
            #     "content": None,
            #     "file_url": image_url,
            #     "file_name": problem["Image_id"]+ '.png',
            #     "content_type": "image/png",
            # }],
            imagery_args={
                # "foundation_image_url": foundation_model_image_url,
                # "bounds_map": bounds_map,
                "question_image_url": image_url,
                "question_file_name": problem["Image_id"] + ".png",
            },
        )
        answer = await self.runner.evaluate(chat_message)
        return answer
