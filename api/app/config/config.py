# config.py

import os
from functools import cached_property
from typing import Dict

from dotenv import load_dotenv
import contextvars
import logging

from ..models.enums import AgentType

load_dotenv("./.env.local-only")
# Configure logging to output to the console at the DEBUG level
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


_is_partner = os.getenv("IS_PARTNER", "False").lower() == "true"

_DEFAULT_USER_INFO = {
    "user_id": "68d0608ad04abf90559d3b75",
    "tenant_id": "pseudo-144cfa41-38ba-4f3f-a184-dc862aa1bc2b",
    "email": None,
    "name": None,
    "is_superuser": True,
    "is_manager": True,
}

class Config:
    # ENV = os.getenv('ENV', 'dev')  # default to 'dev' if ENV is not set
    user_info_var = contextvars.ContextVar("user_info", default=_DEFAULT_USER_INFO)

    # print('--------------------------------------\nConfig() created! ---\n')
    @cached_property
    def CHAT_SLIDING_WINDOW_SIZE(self):
        return int(os.getenv("CHAT_SLIDING_WINDOW_SIZE", 40000))

    # CHAT_SLIDING_WINDOW_SIZE = os.getenv('CHAT_SLIDING_WINDOW_SIZE', 10000)
    # 1K chars ~= 200 tokens
    # 5K chars ~= 1000 tokens
    # 10K chars ~= 3K tokens
    # 20K chars ~= 4K tokens
    # 40K chars ~= 8K tokens

    @cached_property
    def is_partner(self):
        return _is_partner

    @cached_property
    def AWS_ACCESS_KEY_ID(self):
        return os.getenv("AWS_ACCESS_KEY_ID")

    @cached_property
    def AWS_SECRET_ACCESS_KEY(self):
        return os.getenv("AWS_SECRET_ACCESS_KEY")

    @cached_property
    def AWS_REGION(self):
        return os.getenv("AWS_REGION")

    @cached_property
    def BUCKET_NAME(self):
        return os.getenv("FILES_BUCKET_NAME")

    @cached_property
    def managers(self):
        return os.getenv("MANAGERS", "").split(",")

    OPENAI_EMBEDDING_ENGINE = "text-embedding-ada-002"

    @cached_property
    def default_model(self):
        return "gpt-5-chat-latest"

    @cached_property
    def default_project_id(self):
        return "68d0617c5f83766eeb6abb15"

    @cached_property
    def default_cheaper_model(self):
        return "gpt-5-nano"

    @cached_property
    def default_cheaper_and_fast_model(self):
        return "gemini-2.0-flash-lite"

    @cached_property
    def default_cheaper_vision_model(self):
        return "gpt-5-nano"

    @cached_property
    def default_file_model(self):
        return "gemini-2.5-flash-lite"

    @cached_property
    def default_vision_model(self):
        return "gpt-5-chat-latest"

    @cached_property
    def default_image_generation_model(self):
        return "dall-e-3"

    # @property
    # def default_temperature(self):
    #     return 0.1

    @cached_property
    def agents(self):
        return {}

    @cached_property
    def tenants(self):
        return (
            {
                "pseudo-1aaf6311-ab97-4375-8dc5-7267ec232750": {
                    "name": "Test tenant",
                    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                    "can_add_external": True,
                },
                # others..
            }
            if _is_partner
            else {
                "pseudo-144cfa41-38ba-4f3f-a184-dc862aa1bc2b": {
                    "name": "Pseudo Tenant",
                    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                    "can_add_external": True,
                },
            }
        )


    def __init__(self):
        # Perform validation checks and log warnings or raise exceptions if needed
        if not self.AWS_ACCESS_KEY_ID or not self.AWS_SECRET_ACCESS_KEY:
            pass
            # logging.warning("AWS credentials are not set properly.")


# Instantiate the config object
config = Config()

# logging.info('------------
