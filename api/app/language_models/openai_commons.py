import openai

from app.config.config import config


def get_async_client():
    tenant_id = config.user_info_var.get()["tenant_id"]
    return openai.AsyncOpenAI(api_key=config.tenants[tenant_id]["OPENAI_API_KEY"])


def get_client():
    tenant_id = config.user_info_var.get()["tenant_id"]
    return openai.OpenAI(api_key=config.tenants[tenant_id]["OPENAI_API_KEY"])


def get_api_key():
    tenant_id = config.user_info_var.get()["tenant_id"]
    return config.tenants[tenant_id]["OPENAI_API_KEY"]
