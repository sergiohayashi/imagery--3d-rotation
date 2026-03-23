from app.language_models import openai_embedding
from app.language_models.file_utils import download_file_as_byte
from app.services.services_for_rag.spliter_for_text import TextSpliter


class EmbeddingService:

    @staticmethod
    async def split_and_get_embedding_for(file_url, file_name, content_type):

        # split text
        parts, content, file_size = TextSpliter.split(file_name, file_url)

        # generate embedding
        chunks = []
        for p in parts:
            chunks.append(
                dict(
                    content=p["content"],
                    embedding=await openai_embedding.get_embedding(p["content"]),
                    summary=None,
                    source=p["source"],
                )
            )
        return chunks, file_size, openai_embedding.EMBEDDING_MODEL


embedding_service = EmbeddingService()
