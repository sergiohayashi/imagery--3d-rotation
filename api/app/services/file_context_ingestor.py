import datetime
import traceback
from enum import Enum

from bson import ObjectId

from app.database_async import db_async
from app.llm_services.any_model import AnyModel
from app.services import file_context_service
from app.services.services_for_rag.file_spliter import FileSpliter
from app.services.services_for_rag.rag_llm_service import RagLLMService


class FileStatus(str, Enum):
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"


class FileContextIngestorService:

    @staticmethod
    async def ingest_file(file_id: str):
        # print('simulate 10 seconds of processing...')
        # await asyncio.sleep(10)
        # print('simulate 10 seconds of processing...DONE')

        try:
            await FileContextIngestorService._ingest_file(file_id)

        except Exception as e:
            print(f"Error {e}")
            traceback.print_exc()
            # update

    @classmethod
    async def _ingest_file(cls, file_id: str):
        file = await db_async.files.find_one({"_id": ObjectId(file_id)})
        file_context_id = file.get("file_context_id")

        print(f'Processing file: {file.get("file_name")}')

        # create entry in file_context_files, processing_status = 'working'
        inserted = await db_async.file_context_files.insert_one(
            {
                "file_context_id": ObjectId(file_context_id),
                "file_id": ObjectId(file_id),
                "file_url": file.get("file_url"),
                "file_name": file.get("file_name"),
                "content_type": file.get("content_type"),
                "created_at": datetime.datetime.now(datetime.timezone.utc),
                "introduction": None,
                "status": FileStatus.PROCESSING.value,
                "seq_count": 0,
            }
        )
        context_file_id = inserted.inserted_id

        await file_context_service.update_file_count(file_context_id)

        try:
            # generate introduction
            introduction, _ = await RagLLMService.generate_introduction_for_file(
                file.get("file_url"), file.get("file_name"), file.get("content_type")
            )
            await db_async.file_context_files.update_one(
                {"_id": ObjectId(context_file_id)},
                {
                    "$set": {
                        "introduction": introduction,
                    }
                },
            )

            file_url, file_name, file_content = (
                file.get("file_url"),
                file.get("file_name"),
                file.get("content_type"),
            )
            chunks, file_size, embedding_model, full_text = await FileSpliter(
                file_url,
                file_name,
                file_content,
                str(file_context_id),
                str(context_file_id),
            ).split_in_chunks()

            for chunk in chunks:
                obj = {
                    "context_file_id": ObjectId(context_file_id),
                    "created_at": datetime.datetime.now(datetime.timezone.utc),
                    "file_context_id": ObjectId(file_context_id),
                    "project_id": file.get("project_id"),
                    "type": chunk.get("type"),
                    "source": chunk["source"],
                    "embedding": chunk["embedding"],
                    "introduction": chunk["introduction"],
                    "seq": chunk["seq"],
                }
                if chunk["type"] == "text":
                    obj["text"] = {
                        "content": chunk.get("content"),
                    }
                elif chunk["type"] == "image":
                    obj["image"] = {
                        "image_url": chunk.get("image_url"),
                        "ext": chunk.get("ext"),
                        "caption": chunk.get("caption"),
                    }

                await db_async.file_context_chunks.insert_one(obj)

            await db_async.file_context_files.update_one(
                {"_id": ObjectId(context_file_id)},
                {
                    "$set": {
                        "status": FileStatus.PROCESSED.value,
                        "file_size": file_size,
                        "seq_count": (
                            chunks[-1]["seq"] if len(chunks) > 0 else 0
                        ),  # last chunk sequence number
                    }
                },
            )

        except Exception as error:
            traceback.print_exc()
            await db_async.file_context_files.update_one(
                {"_id": ObjectId(context_file_id)},
                {
                    "$set": {
                        "status": FileStatus.ERROR.value,
                        "error": {
                            "type": type(error).__name__,
                            "message": str(error),
                            "traceback": traceback.format_exc(),
                        },
                    }
                },
            )
        print(f'Processing file: {file.get("file_name")} DONE')
