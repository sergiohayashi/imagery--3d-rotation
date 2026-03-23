from bson import ObjectId

from app.cli.commands.helpers.command_base import CommandBase
from app.models.chat_message import ChatMessage, ModelWithParameters
from app.services.chat_message_service import ChatMessageService


def register(subparsers):
    parser = subparsers.add_parser("chat1")
    parser.set_defaults(handler=ChatRunner1)


class ChatRunner1(CommandBase):
    def __init__(self, args):
        super().__init__()
        self.args = args

    async def __call__(self):
        chat_message: ChatMessage = ChatMessage(
            chat_id=str(ObjectId()),  # new
            project_id=self.project_id,  # define in base class
            message="Hello!",
            use_model=[ModelWithParameters(name="gpt-4o-mini-2024-07-18")],
        )
        response = await ChatMessageService().chat(chat_message)
        print(
            "response",
            response.model_dump() if hasattr(response, "model_dump") else response,
        )
