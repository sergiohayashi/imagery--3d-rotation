from enum import Enum


class ChatRole(str, Enum):
    system = "system"
    assistant = "assistant"
    user = "user"


class AgentType(str, Enum):
    echo_agent = "echo-agent"
    simple_chat = "simple-chat"
    retrieval_agent = "retrieval-agent"
    google_search = "google-search"
    send_email = "send-email"
