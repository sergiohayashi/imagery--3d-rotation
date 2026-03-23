from typing import List

from pymongo import DESCENDING

from app.database_async import db_async

TOP_K = 5


class ChunkTextSearch:

    @staticmethod
    async def text_search_for_terms(terms: list | str, top_k: int = TOP_K):
        if not terms:
            return []

        if isinstance(terms, list):
            # apply as AND on the word
            terms = " ".join([f'"{w}"' for w in terms])

        cursor = (
            db_async.file_context_chunks.find(
                {"$text": {"$search": terms}},
                {"score": {"$meta": "textScore"}, "content": 1},
            )
            .sort("score", DESCENDING)
            .limit(TOP_K)
        )

        result = [
            {"id": str(d["_id"]), "content": d.get("content")} async for d in cursor
        ]
        return result
