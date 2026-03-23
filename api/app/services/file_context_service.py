import datetime
import traceback

from bson import ObjectId
from fastapi import HTTPException
from pymongo import DESCENDING
from starlette import status

from app.config.auth_guard import for_project
from app.config.config import config
from app.database_async import db_async
from app.models.file_context import FileContext
from app.services.s3_services import S3UploadServices


async def get_all(project_id):
    for_project(project_id)

    cursor = db_async.file_context.find({"project_id": ObjectId(project_id)}).sort(
        "created_at", DESCENDING
    )

    result = [
        {
            "id": str(c["_id"]),
            "title": c["title"],
            "file_count": c.get("file_count", 0),
        }
        async for c in cursor
    ]
    return result


async def create_new(args: FileContext):
    user_id = config.user_info_var.get().get("user_id")
    inserted = await db_async.file_context.insert_one(
        {
            "title": args.title,
            "project_id": ObjectId(args.project_id),
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "created_by_user_id": user_id,
        }
    )
    return str(inserted.inserted_id)


async def get_one(id):
    return None


async def delete_file_context(file_context_id: str):
    file_context = await db_async.file_context.find_one(
        {"_id": ObjectId(file_context_id)}
    )
    if not file_context:
        raise HTTPException(
            detail="Invalid id", status_code=status.HTTP_400_BAD_REQUEST
        )
    for_project(str(file_context["project_id"]))

    # get all the files
    cursor = db_async.file_context_files.find(
        {"file_context_id": ObjectId(file_context_id)}, {"_id": 1}
    )

    # delete each file. Ignore in case of error
    async for f in cursor:
        _id = str(f["_id"])
        print(f"Deleting file {_id}...")
        try:
            await delete_file(file_context_id, _id)
        except Exception as e:
            print(f"Error deleting file {_id}. Ignore and continue", e)
            traceback.print_exc()

    # delete file context
    print(f"Deleting file context...")
    await db_async.file_context.delete_one({"_id": ObjectId(file_context_id)})

    await update_file_count(file_context_id)
    print("Delete done!")


async def delete_file(context_id: str, file_id: str):
    file_context = await db_async.file_context.find_one({"_id": ObjectId(context_id)})
    if not file_context:
        raise HTTPException(
            detail="Invalid id", status_code=status.HTTP_400_BAD_REQUEST
        )
    for_project(str(file_context["project_id"]))

    # load file
    f = await db_async.file_context_files.find_one({"_id": ObjectId(file_id)})
    if not f:
        raise HTTPException(
            detail="Invalid id", status_code=status.HTTP_400_BAD_REQUEST
        )

    # delete file object on s3 and db
    await S3UploadServices.safe_delete_file(f.get("file_url"))

    # delete image files in chunk (extracted from pdf)
    cursor = db_async.file_context_chunks.find({"context_file_id": ObjectId(file_id)})
    async for chunk in cursor:
        image_url = chunk.get("image", {}).get("image_url")
        if image_url:
            await S3UploadServices.safe_delete_file(image_url)

    # delete chunks and context_file
    await db_async.file_context_chunks.delete_many(
        {"context_file_id": ObjectId(file_id)}
    )

    # delete context file
    await db_async.file_context_files.delete_one({"_id": ObjectId(file_id)})

    await update_file_count(context_id)
    print(f"file {file_id} deleted!")


async def get_files(file_context_id: str):
    file_context = await db_async.file_context.find_one(
        {"_id": ObjectId(file_context_id)}
    )
    if not file_context:
        raise HTTPException(
            detail="Invalid id", status_code=status.HTTP_400_BAD_REQUEST
        )
    for_project(str(file_context["project_id"]))

    cursor = db_async.file_context_files.find(
        {"file_context_id": ObjectId(file_context_id)},
        {
            "_id": 1,
            "file_url": 1,
            "file_name": 1,
            "status": 1,
            "created_at": 1,
            "file_size": 1,
            "error": 1,
        },
    ).sort("created_at", DESCENDING)

    result = [
        {
            "id": str(d.get("_id")),
            "file_name": d.get("file_name"),
            "file_url": d.get("file_url"),
            "content_type": d.get("content_type"),
            "created_at": d.get("created_at"),
            "file_size": d.get("file_size"),
            "status": d.get("status"),
            "error": d.get("error", {}).get("message", None),
        }
        async for d in cursor
    ]
    return result


async def update(_id, args):
    file_context = await db_async.file_context.find_one({"_id": ObjectId(_id)})
    if not file_context:
        raise HTTPException(
            detail="Invalid id", status_code=status.HTTP_400_BAD_REQUEST
        )
    for_project(str(file_context["project_id"]))

    await db_async.file_context.update_one(
        {"_id": file_context.get("_id")},
        {
            "$set": {
                "title": args.title,
            }
        },
    )


async def update_file_count(file_context_id):
    count = await db_async.file_context_files.count_documents(
        {"file_context_id": ObjectId(file_context_id)}
    )
    await db_async.file_context.update_one(
        {"_id": ObjectId(file_context_id)},
        {
            "$set": {
                "file_count": count,
            }
        },
    )
