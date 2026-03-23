from bson import ObjectId

from app.database_async import db_async
from app.services.services_for_rag.prompt_loader import get_prompt
from app.services.services_for_rag.semantic_search import semantic_search
from app.services.services_for_rag.text_search import ChunkTextSearch

TOP_K = 1


class RagContextBuilderWithTextSearch:

    @staticmethod
    async def build_context(chat_history, prompt: str, rag_context_id: str):

        # semantic search
        semantic_docs, terms_keyword = await semantic_search(
            chat_history, prompt, rag_context_id
        )
        print(">> semantic docs: ", semantic_docs)

        # keyword search
        if terms_keyword:
            keyword_docs = await ChunkTextSearch.text_search_for_terms(terms_keyword)
        else:
            keyword_docs = []
        print(">> keyword docs: ", terms_keyword)

        # merge list..
        docs_id = [d["id"] for d in semantic_docs]
        for d in keyword_docs:
            if d["id"] not in docs_id:
                docs_id.append(d["id"])

        print(">> union, before trim: ", docs_id)

        # triagem
        # filtered_docs = ...

        if not docs_id:
            return []

        # only top k
        docs_id = docs_id[:TOP_K]
        print(">> union, AFTER TOP-K trim: ", docs_id)

        # load content and source
        cursor = db_async.file_context_chunks.find(
            {"_id": {"$in": [ObjectId(_id) for _id in docs_id]}},
            {"content": 1, "source": 1},
        )

        entries = [
            dict(role="system", content=get_prompt("system_message_for_rag.txt"))
        ]
        async for doc in cursor:
            entries.append(
                dict(
                    role="user",
                    content=f'====BEGIN REFERENCE====\nREFERENCE SOURCE: {doc["source"]}\nREFERENCE CONTENT: \n{doc["content"]}\n====END REFERENCE====',
                )
            )

        return entries
