import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("./.env.local-only")


class DB:
    def __init__(self):
        # load_dotenv('./.env.local')
        if os.getenv("MONGO_USERNAME"):
            self.client = MongoClient(
                os.getenv("MONGO_URL"),
                username=os.getenv("MONGO_USERNAME"),
                password=os.getenv("MONGO_PASSWORD"),
            )
        else:
            self.client = MongoClient(os.getenv("MONGO_URL"))
        self.db = self.client[os.getenv("MONGO_DBNAME")]
        self.projects = self.db["projects"]
        self.users = self.db["users"]
        self.users_usage = self.db["users_usage"]
        self.user_projects = self.db["user_projects"]
        self.context_artifacts = self.db["context_artifacts"]
        self.chats = self.db["chats"]
        self.chat_entries = self.db["chat_entries"]
        self.rate_limits = self.db["rate_limits"]
        self.prompts = self.db["prompts"]
        self.system_messages = self.db["system_messages"]
        self.usage_log = self.db["usage_log"]
        self.prompt_templates = self.db["prompt_templates"]
        self.augmented_message_log = self.db["augmented_message_log"]
        self.agent_action = self.db["agent_action"]
        self.agent_action_step = self.db["agent_action_step"]
        self.discover = self.db["discover"]
        self.bookmarks = self.db["bookmarks"]
        self.chat_view = self.db["chat_view"]
        self.feedbacks = self.db["feedbacks"]
        self.feedback_comments = self.db["feedback_comments"]
        self.users_activity_log = self.db["users_activity_log"]


db = DB()
