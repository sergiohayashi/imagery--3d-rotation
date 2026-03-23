import datetime
import traceback

from bson import ObjectId
from fastapi import HTTPException
from pymongo import DESCENDING
from starlette import status

from app.database_async import db_async
from app.config.config import config
from app.models.file_category import FileCategory
from app.services.chat_service import ChatService
from app.services.s3_services import S3UploadServices


class FileServices:
    @classmethod
    async def delete_entry(cls, file_url):
        print("Delete file: ", file_url)
        result = await db_async.files.delete_one({"file_url": file_url})
        print("delete result", result)

    @classmethod
    async def add_entry(
        cls,
        file_url,
        content_type,
        file_name,
        category,
        project_id=None,
        chat_id=None,
        file_context_id: str = None,
    ):
        context = config.user_info_var.get()
        inserted = await db_async.files.insert_one(
            {
                "file_url": file_url,
                "category": category.value,
                "user_id": context.get("user_id"),
                "created_chat_id": chat_id or context.get("chat_id"),
                "tenant_id": context.get("tenant_id"),
                "project_id": project_id or context.get("project_id"),
                "content_type": content_type,
                "file_context_id": file_context_id,
                "file_name": file_name,
                "create_at": datetime.datetime.now(datetime.timezone.utc),
            }
        )
        return str(inserted.inserted_id)

    @classmethod
    async def get_all_files(
        cls, project_id: str, category: str, start: int = 0, size: int = 20
    ):
        """
        Get the list of files, for the current project_id, owned by the current user
        :return:
        """
        context = config.user_info_var.get()
        user_id = context.get("user_id")

        query = {"user_id": user_id, "project_id": project_id, "category": category}

        cursor = (
            db_async.files.find(query)
            .sort("create_at", DESCENDING)
            .skip(start)
            .limit(size)
        )

        result = [
            {
                "id": str(e.get("_id")),
                "file_url": e.get("file_url"),
                "chat_id": e.get("created_chat_id"),
                "content_type": e.get("content_type"),
                "file_name": e.get("file_name"),
                "created_at": e.get("create_at"),
            }
            async for e in cursor
        ]
        return result

    @classmethod
    async def delete_file_and_chat(cls, _id: str):
        context = config.user_info_var.get()
        user_id = context.get("user_id")

        query = {
            "user_id": user_id,
            "_id": ObjectId(_id),
        }
        f = await db_async.files.find_one(query)
        if not f:
            raise HTTPException(
                detail="file not found", status_code=status.HTTP_400_BAD_REQUEST
            )

        # delete chat (consider the case the chat don't exist..
        try:
            print(f"Try delete chat {f.get('created_chat_id')}")
            await ChatService.delete(f.get("created_chat_id"))
        except Exception as e:
            print(f"Error occurred: {e}. Continue..")
            traceback.print_exc()

        # delete fine entry, if it has not deleted with the chat
        f = await db_async.files.find_one(query)
        if f and f.get("file_url"):
            await S3UploadServices.safe_delete_file(f.get("file_url"))
