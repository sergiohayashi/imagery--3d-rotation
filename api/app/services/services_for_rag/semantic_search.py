import numpy as np
from bson import ObjectId

from app.database_async import db_async
from app.language_models.openai_embedding import get_embedding
from app.services.services_for_rag.rag_llm_service import RagLLMService
from app.services.services_for_rag.semantic_search_in_memory import (
    Document,
    SemanticSearchInMemory,
    SIMILARITY_THRESHOLDS,
)


async def semantic_search(chat_history, prompt, rag_context_id: str, top_k: int = 5):
    # improve prompt, and generate keyword list..
    semantic_prompt, terms_keywords, meta = (
        await RagLLMService.review_prompt_for_semantic_search_and_keywords(
            chat_history, prompt
        )
    )

    # improve prompt
    print(f"Generating embedding for {prompt[:30]}...")
    prompt_embedding = await get_embedding(semantic_prompt)

    # load the files in memory
    print("Loading chunks...")
    chunks = await db_async.file_context_chunks.find(
        {"file_context_id": ObjectId(rag_context_id)}, {"embedding": 1}
    ).to_list(None)

    documents = [
        Document(
            id=str(c.get("_id")),
            # content = c.get('content'),
            embedding=np.array(c.get("embedding")),
            # source = c.get('source')
        )
        for c in chunks
    ]

    if len(documents) <= 0:
        return [], terms_keywords, semantic_prompt

    print(f"{len(documents)} documents found in the chunk. Do semantic search...")
    search_engine = SemanticSearchInMemory(documents)
    relevant_chunks = search_engine.search(
        np.array(prompt_embedding),
        threshold=SIMILARITY_THRESHOLDS["experimental_low"],
        top_k=top_k,
    )

    return (
        [{"id": d.id} for d, score in relevant_chunks],
        terms_keywords,
        semantic_prompt,
    )

    # # load content and source
    # cursor = db_async.file_context_chunks.find(
    #     { "_id": {"$in": [ObjectId(d.id) for d,score in relevant_chunks]}},
    #     { "content": 1, "source": 1}
    # )
    #
    # # result
    # result = [{
    #     "id": str(d["_id"]),
    #     # "content": d['content'],
    #     # "source": d['source']
    # } async for d in cursor]
    # return result, terms_keywords
    #
