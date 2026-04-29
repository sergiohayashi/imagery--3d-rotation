import logging
from pathlib import Path
from bson import ObjectId
import datetime
import json

from app.cli.commands.helpers.command_base import CommandBase
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.services.chat_message_service import ChatMessageService


def register(subparsers):
    parser = subparsers.add_parser("chat_gpt_5_2")
    parser.add_argument("--start", required=False)
    parser.add_argument("--end", required=False)
    parser.add_argument("--list", required=False)
    parser.set_defaults(handler=ChatRunner_GPT_5_2)


class ChatRunner_GPT_5_2(CommandBase):

    root_path = Path(
        # "/home/hayashi/phd/imagery/projects/simplechat/problems/spatialviz/dataset-eval2-1001--3d-rotation-level-0"
        "/home/hayashi/phd/imagery/projects/imagery--3d-rotation/data/spatialviz"
    )

    # root_path = Path(
    #     "/home/hayashi/phd/imagery/projects/imagery--3d-rotation/data/spatialviz"
    #     # "/home/hayashi/phd/imagery/projects/simplechat/problems/spatialviz/dataset-eval2-1001--3d-rotation-level-0"
    # )

    def __init__(self, args):
        super().__init__()
        self.args = args

    async def __call__(self):

        # read the problems
        # with open(Path(self.root_path / "problems/dataset-eval2-1001--3d-rotation-level-0", "problems.json")) as f:
        #     problems = json.load(f)

        with open(Path(self.root_path, "problems", "problems.json")) as f:
            problems = json.load(f)


        # create a folder under root_path, with the patter result_yyyymmdd_hhmmss
        eval_id = (
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            + "_"
            + self.__class__.__name__
        )
        result_dir = self.root_path / "results" / f"result_{eval_id}"
        print(f"\nResult directory: {result_dir}")
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
        question = "The left image shows the original cube stack made of equal-sized small cubes. Which of the options on the right cannot be obtained by rotating the original cube stack? Please answer from options A, B or C. Generate only the answer (the letter, without any other text)"

        for idx, problem in enumerate(problems_to_eval):
            logging.info(f"\n{'*'*30} Problem {problem['Image_id']} {'*'*30}\n")

            # create the chat title for this problem
            problem_id = f"{problem['Category']}-{problem['Task']}-{problem['Level']}-{problem['Image_id']}"
            title = f"{eval_id}--{problem_id}"
            image_id = f"{problem['Image_id']}"

            # image_url = f"file://{Path(self.root_path / "problems/dataset-eval2-1001--3d-rotation-level-0/images", image_id)}.png"
            image_url = (
                f"file://{Path(self.root_path, "problems", "images", image_id)}.png"
            )

            try:
                chat_message: ChatMessage = ChatMessage(
                    chat_id=str(ObjectId()),  # new
                    project_id=self.project_id,  # define in base class
                    title=title,
                    message=f"Question: {question}",
                    use_model=[ModelWithParameters(name="gpt-5.2-2025-12-11")],
                    preset_list=[
                        {
                            "role": "user",
                            "content": None,
                            "file_url": image_url,
                            "file_name": problem["Image_id"] + ".png",
                            "content_type": "image/png",
                        }
                    ],
                )

                response = await ChatMessageService().chat(chat_message)
                print(f"Response: {response}")
                answer = response.response
                result.append(
                    {
                        "problem_id": problem_id,
                        "title": title,
                        "answer": answer,
                        "expected": problem["Answer"],
                        "correct": answer == problem["Answer"],
                    }
                )
                print(result[-1])
                if answer == problem["Answer"]:
                    score += 1
            except Exception as e:
                logging.exception(f"Error: {e}")
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
