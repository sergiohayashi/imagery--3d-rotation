# routes/s3_services.py
import datetime
import logging
import os
import traceback
import uuid
from enum import Enum
from pathlib import Path
import re

import boto3
from fastapi import HTTPException, UploadFile
from starlette import status

from app.models.file_category import FileCategory
from app.utils.file_utils import guess_content_type_from_filename
from ..config.config import config
from ..config.global_config import the_global_config
from ..database_async import db_async

logger = logging.getLogger(__name__)

# Initialize the boto3 client with your AWS credentials
s3_client = boto3.client(
    "s3",
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY,
    region_name=config.AWS_REGION,
)

# Define the bucket name where you want to upload files
BUCKET_NAME = config.BUCKET_NAME
UPLOAD_BUCKET_NAME = config.BUCKET_NAME


def short_guid(guid: str):
    return guid[:8] + "-" + guid[-8:]


def generate_s3key_for_file_context_chunk(
    filename: str, file_context_id: str, file_id: str
):
    user_info = config.user_info_var.get()
    user_id = user_info.get("user_id")
    tenant_id = user_info.get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail=f"invalid credentials")

    s3key = f"{short_guid(tenant_id)}/{short_guid(user_id)}/{FileCategory.FILE_CONTEXT.value}/{file_context_id}/c/{file_id}/{filename}"
    return s3key


def generate_s3key_for(filename: str, cat: FileCategory, file_context_id: str = None):
    user_info = config.user_info_var.get()
    user_id = user_info.get("user_id")
    tenant_id = user_info.get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail=f"invalid credentials")

    if cat == FileCategory.FILE_CONTEXT:
        if not file_context_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file context id",
            )
        s3key = f"{short_guid(tenant_id)}/{short_guid(user_id)}/{cat.value}/{file_context_id}/{filename}"
    else:
        s3key = f"{short_guid(tenant_id)}/{short_guid(user_id)}/{cat.value}/{filename}"
    return s3key


def is_owner(file_url: str):
    user_info = config.user_info_var.get()
    user_id = user_info.get("user_id")
    tenant_id = user_info.get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail=f"invalid credentials")

    match_text = f"{short_guid(tenant_id)}/{short_guid(user_id)}"
    return match_text in file_url


def unique_filename_of(filename):
    # Split the filename into base and extension
    base, ext = os.path.splitext(filename)

    # Remove disallowed characters: anything except letters, numbers, underscore, and dot
    safe_base = re.sub(r"[^A-Za-z0-9_.]", "", base)

    # Generate a unique GUID (hexadecimal representation without dashes)
    unique_id = uuid.uuid4().hex

    # Concatenate the GUID to the original file name
    new_filename = f"{safe_base}_{unique_id}{ext}"
    return new_filename


class _FileServices:
    @classmethod
    async def delete_entry(cls, file_url):
        print("Delete file: ", file_url)
        result = await db_async.files.delete_one({"file_url": file_url})
        print("delete result", result)

    @classmethod
    async def add_entry(
        cls, file_url, content_type, file_name, category, project_id=None, chat_id=None
    ):
        context = config.user_info_var.get()
        await db_async.files.insert_one(
            {
                "file_url": file_url,
                "category": category.value,
                "user_id": context.get("user_id"),
                "created_chat_id": chat_id or context.get("chat_id"),
                "tenant_id": context.get("tenant_id"),
                "project_id": project_id or context.get("project_id"),
                "content_type": content_type,
                "file_name": file_name,
                "create_at": datetime.datetime.now(datetime.timezone.utc),
            }
        )


class S3UploadServices:
    # @staticmethod
    # async def upload_image(file: UploadFile, cat: FileCategory):
    #     file_name = generate_s3key_for(f"{uuid.uuid4()}-{file.filename}", cat)
    #     try:
    #         # Read the file content
    #         file_content = file.file.read()
    #
    #         # Upload the file to S3
    #         file_extension = Path(file.filename).suffix.lstrip('.')
    #         content_type = f'image/{file_extension}' if file_extension.lower() in ['jpg', 'jpeg', 'png', 'gif'] else 'application/octet-stream'
    #
    #         s3_client.put_object(Bucket=BUCKET_NAME,
    #                              Key=file_name,
    #                              Body=file_content,
    #                              ContentDisposition='inline',
    #                              ContentType=content_type
    #                              )
    #
    #         return f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_name}"
    #
    #     except Exception as e:
    #         logger.error(f"An error occurred: {e}")
    #         raise HTTPException(status_code=500, detail="An error occurred while uploading the file.")

    # @classmethod
    # async def upload_any_file(cls, file_bytes, content_type, original_filename, cat: FileCategory):
    #     file_name = generate_s3key_for(f"{uuid.uuid4()}-{original_filename}", cat)
    #     try:
    #         s3_client.put_object(Bucket=BUCKET_NAME,
    #                              Key=file_name,
    #                              Body=file_bytes,
    #                              ContentDisposition='inline',
    #                              ContentType=content_type
    #                              )
    #
    #         file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_name}"
    #         return file_url
    #     except Exception as e:
    #         logger.error(f"An error occurred: {e}")
    #         raise HTTPException(status_code=500, detail="An error occurred while uploading the file.")

    @staticmethod
    async def upload_generate_image(
        file_name: str, file_content: bytes, file_extension: str, cat: FileCategory
    ):
        s3_key = generate_s3key_for(file_name, cat)
        content_type = (
            f"image/{file_extension}"
            if file_extension.lower() in ["jpg", "jpeg", "png", "gif"]
            else "application/octet-stream"
        )
        try:
            if the_global_config.use_local_files:
                from .s3_services_local_file_version import (
                    save_file_locally_under_s3_key,
                )

                file_path = save_file_locally_under_s3_key(s3_key, file_content)
                file_url = f"file://{file_path}"
                await _FileServices.add_entry(
                    file_url, content_type, s3_key, FileCategory.GENERATED
                )
                return file_url

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=file_content,
                ContentDisposition="inline",
                ContentType=content_type,
            )

            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
            await _FileServices.add_entry(
                file_url, content_type, s3_key, FileCategory.GENERATED
            )
            return file_url

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise HTTPException(
                status_code=500, detail="An error occurred while uploading the file."
            )

    @staticmethod
    async def upload_generate_file(
        file_name: str,
        file_content: bytes,
        cat: FileCategory,
        content_type=None,
        name_is_already_unique=False,
    ):
        if not name_is_already_unique:
            file_name = unique_filename_of(file_name)
        file_name = generate_s3key_for(file_name, cat)

        if not content_type:
            _, ext = os.path.splitext(file_name)
            content_type = (
                f"image/{ext}"
                if ext.lower() in ["jpg", "jpeg", "png", "gif"]
                else "application/octet-stream"
            )

        try:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=file_name,
                Body=file_content,
                ContentDisposition="inline",
                ContentType=content_type,
            )

            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_name}"
            print("File upload to: ", file_url)
            await _FileServices.add_entry(
                file_url, content_type, file_name, FileCategory.GENERATED
            )
            return file_url

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise HTTPException(
                status_code=500, detail="An error occurred while uploading the file."
            )

    @staticmethod
    async def upload_image_file_from_local(
        local_file_path: str,
        content_type: str = None,
    ):
        if not content_type:
            content_type = guess_content_type_from_filename(local_file_path)

        file_content = open(local_file_path, "rb").read()
        file_name = os.path.basename(local_file_path)

        file_name = generate_s3key_for(file_name, FileCategory.UPLOAD)

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=file_name,
            Body=file_content,
            ContentDisposition="inline",
            ContentType=content_type,
        )

        file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_name}"
        print("File upload to: ", file_url)
        await _FileServices.add_entry(
            file_url, content_type, file_name, FileCategory.UPLOAD
        )
        return file_url

    @staticmethod
    async def upload_file_context_extracted_image(
        file_name: str,
        file_content: bytes,
        file_context_id: str,
        file_id: str,
        content_type: str = None,
    ):
        file_name = generate_s3key_for_file_context_chunk(
            file_name, file_context_id, file_id
        )

        if not content_type:
            _, ext = os.path.splitext(file_name)
            content_type = (
                f"image/{ext}"
                if ext.lower() in ["jpg", "jpeg", "png", "gif"]
                else "application/octet-stream"
            )

        try:
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=file_name,
                Body=file_content,
                ContentDisposition="inline",
                ContentType=content_type,
            )

            file_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_name}"
            print("File upload to: ", file_url)
            await _FileServices.add_entry(
                file_url, content_type, file_name, FileCategory.GENERATED
            )
            return file_url

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise HTTPException(
                status_code=500, detail="An error occurred while uploading the file."
            )

    @staticmethod
    async def safe_delete_file(image_url: str):
        try:
            if image_url.startswith("file://"):
                from .s3_services_local_file_version import delete_file_locally

                file_path = image_url[7:]
                delete_file_locally(file_path)
                await _FileServices.delete_entry(image_url)
                print(f"File {image_url} deleted successfully")
                return {"detail": "Image deleted successfully."}

            # expected:
            # https://images.s3.sa-east-1.amazonaws.com/files/surprise_6b0482777c2344b99e8d8a71eb2307a5.pdf
            # https://images.s3.amazonaws.com/files/surprise_6b0482777c2344b99e8d8a71eb2307a5.pdf
            # https://images.s3.amazonaws.com/surprise_6b0482777c2344b99e8d8a71eb2307a5.pdf
            # https://files-dev.s3.amazonaws.com/63b19fa5-edb09eab/652ef3a3-efee869d/g/1360e0052fd94811ab1938e9435dae27.mp4
            # split to 'http', '', '....amazon.com', '..key part ..', '...'
            key = "/".join(image_url.split("/")[3:])
            print(f"safe_delete_file: url={image_url} key={key}")
            s3_client.delete_object(Bucket=BUCKET_NAME, Key=key)
            await _FileServices.delete_entry(image_url)

            print(f"File {image_url} deleted successfully")
            return {"detail": "Image deleted successfully."}
        except Exception as e:
            logger.error(f"An error occurred while deleting image: {e}")
            traceback.print_exc()
            # raise HTTPException(status_code=500, detail="An error occurred while deleting the image.")

    @staticmethod
    async def delete_if_owner(file_url: str):
        if not is_owner(file_url):
            raise HTTPException(status_code=401, detail=f"Not owner")
        await S3UploadServices.safe_delete_file(file_url)
