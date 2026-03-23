from typing import List

from bson import ObjectId

from app.database_async import db_async
from app.services.services_for_rag.prompt_loader import get_prompt
from app.services.services_for_rag.rag_llm_service import RagLLMService
from app.services.services_for_rag.semantic_search import semantic_search

TOP_K = 5
FULL_FILE_LIMIT_FOR_PDF = 32000000  # 10Mb
FULL_FILE_LIMIT_FOR_TEXT = 500000  # 500K bytes


async def check_files_to_include_in_full(
    rag_context_id, prompt_with_context
) -> List[ObjectId]:

    # get list of files, with file name and introduction, exclude file larger than LIMIT
    files = await db_async.file_context_files.find(
        {"file_context_id": ObjectId(rag_context_id)}
    ).to_list(None)

    # filter per file size
    filtered = []
    for f in files:
        if "pdf" in f.get("content_type"):
            if f.get("file_size") > FULL_FILE_LIMIT_FOR_PDF:
                print(
                    f'Skip file {f.get("file_name")}. Size ({f.get("file_size")})> Limit'
                )
                continue
        else:
            if f.get("file_size") > FULL_FILE_LIMIT_FOR_TEXT:
                print(
                    f'Skip file {f.get("file_name")}. Size ({f.get("file_size")})> Limit'
                )
                continue
        filtered.append(f)
    files = filtered

    # create list of files
    files_list = [
        dict(file_name=f.get("file_name"), introduction=f.get("introduction"))
        for f in files
    ]

    # ask to llm, pickup files deeply related to the question, and that need to be included in full
    selected_list = await RagLLMService.ask_for_relevant_files(
        prompt_with_context, files_list
    )
    print("check_files_to_include_in_full: received selected list: ", selected_list)
    files_id = [f["_id"] for index, f in enumerate(files) if index in selected_list]
    print("check_files_to_include_in_full: converted file id: ", files_id)

    # return list of files
    return files_id


class VanillaRag:

    @staticmethod
    async def generate_rag_context(chat_history, prompt: str, rag_context_id: str):

        # search_result = [chunk_id1, chunk_id2...]
        search_result_chunks, _, prompt_with_context = await semantic_search(
            chat_history, prompt, rag_context_id, TOP_K
        )

        # load the file id and sequence for each chunk
        id_with_file = await db_async.file_context_chunks.find(
            {"_id": {"$in": [ObjectId(d["id"]) for d in search_result_chunks]}},
            {"context_file_id": 1, "seq": 1},
        ).to_list(None)

        # Now, search for the cases that the file is better to be included in full context
        include_full_files_id = await check_files_to_include_in_full(
            rag_context_id, prompt_with_context
        )
        print("generate_rag_context: Final list of files id:", include_full_files_id)

        # filter and exclude from the chunk list, the chunks that are of the files to be included in full
        print("generate_rag_context: list of chunks BEFORE file filter:", id_with_file)
        id_with_file = [
            d for d in id_with_file if d["context_file_id"] not in include_full_files_id
        ]
        print("generate_rag_context: list of chunks AFTER file filter:", id_with_file)

        # sort by file=>seq
        id_with_file = sorted(
            id_with_file, key=lambda x: (x["context_file_id"], x["seq"])
        )
        chunks_id = [d["_id"] for d in id_with_file]
        print("generate_rag_context: Final list of chunks id:", chunks_id)

        entries = []
        if search_result_chunks:
            entries.append(
                dict(role="system", content=get_prompt("system_message_for_rag.txt"))
            )

            # include entire files
            file_cursor = db_async.file_context_files.find(
                {"_id": {"$in": [ObjectId(_id) for _id in include_full_files_id]}}
            )
            async for f in file_cursor:
                entries.append(
                    dict(
                        role="user",
                        file_url=f.get("file_url"),
                        content_type=f.get("content_type"),
                        file_name=f.get("file_name"),
                    )
                )

            # include chunks
            cursor = db_async.file_context_chunks.find(
                {"_id": {"$in": chunks_id}}, {"embedding": 0}
            )
            async for doc in cursor:
                if doc["type"] == "text":
                    content = doc.get("text", {}).get("content")
                    entries.append(
                        dict(
                            role="user",
                            content=f'====BEGIN REFERENCE====\nREFERENCE SOURCE: {doc["source"]}\nREFERENCE CONTENT: \n{content}\n====END REFERENCE====',
                        )
                    )
                elif doc["type"] == "image":
                    entries.append(
                        dict(
                            role="user",
                            content=f'====THE NEXT IMAGE IS A REFERENCE====\nREFERENCE SOURCE: {doc["source"]}\n',
                        )
                    )
                    entries.append(
                        dict(
                            role="user", image_url=doc.get("image", {}).get("image_url")
                        )
                    )

        return entries
