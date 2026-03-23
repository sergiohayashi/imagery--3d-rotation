import time

from app.language_models.openai_commons import get_async_client
from app.language_models.types.LLMNames import LLMNames
from app.language_models.types.models import ModelDeclaration
from app.services.usage_log_service import UsageLogService

EMBEDDING_MODEL = "text-embedding-3-small"


model_info = {
    "text-embedding-3-small": ModelDeclaration(
        name="text-embedding-3-small",
        company=LLMNames.OPENAI,
        input_price=0.02,
        eligible=True,
    )
}


async def get_embedding(text):
    start_t = time.time()

    print(f"Gerando embedding para [{text[:100]}...]")
    response = await get_async_client().embeddings.create(
        input=text, model=EMBEDDING_MODEL
    )
    embedding = response.data[0].embedding

    meta = response.model_dump()
    meta = {k: v for k, v in meta.items() if k != "data"}  # exclude data..
    meta["elapsed_in_sec"] = time.time() - start_t
    meta["estimate_price"] = round(
        meta["usage"]["prompt_tokens"]
        * model_info[EMBEDDING_MODEL].input_price
        / 1000000.0,
        4,
    )
    meta["company"] = LLMNames.OPENAI.name
    UsageLogService.register_usage_meta(meta, LLMNames.OPENAI)
    return embedding
