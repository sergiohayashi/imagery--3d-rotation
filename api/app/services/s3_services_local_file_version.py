# routes/local_file_services.py
import datetime
import logging
import os
import re
import traceback
import uuid
from pathlib import Path

from fastapi import HTTPException

from app.models.file_category import FileCategory
from app.utils.file_utils import guess_content_type_from_filename
from ..config.config import config
from ..config.global_config import the_global_config
from ..database_async import db_async

logger = logging.getLogger(__name__)


def short_guid(guid: str):
    return guid[:8] + "-" + guid[-8:]


def generate_filename_with_timestamp(filename: str):
    """
    Generate filename with timestamp and microseconds.
    Example: 'dog.png' becomes 'dog-20240115143022-123456.png'
    """
    base, ext = os.path.splitext(filename)

    # Remove disallowed characters: anything except letters, numbers, underscore, hyphen, and dot
    safe_base = re.sub(r"[^A-Za-z0-9_.-]", "", base)

    # Generate timestamp with microseconds (YYYYMMDDHHMMSS-MMMMMM)
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    microseconds = now.strftime("%f")  # 6 digits of microseconds

    # Concatenate to create unique filename
    new_filename = f"{safe_base}-{timestamp}-{microseconds}{ext}"
    return new_filename


def get_local_root_dir():
    """Get the root directory for local files from global config."""
    root_dir = the_global_config.local_files_root_dir
    if not root_dir:
        raise HTTPException(
            status_code=500, detail="local_files_root_dir not configured"
        )

    # Create directory if it doesn't exist
    Path(root_dir).mkdir(parents=True, exist_ok=True)
    return root_dir


def save_file_locally(filename: str, file_content: bytes):
    """
    Save file to local filesystem in the configured root directory.
    Returns the file path.
    """
    root_dir = get_local_root_dir()
    unique_filename = generate_filename_with_timestamp(filename)
    file_path = os.path.join(root_dir, unique_filename)

    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
        return file_path
    except Exception as e:
        logger.error(f"Error saving file locally: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while saving the file."
        )


def save_file_locally_under_s3_key(s3_key: str, file_content: bytes) -> str:
    """
    Save bytes under ``local_files_root_dir`` using the same relative path layout as an S3 object key
    (tenant/user/category/.../filename). Returns the absolute filesystem path.
    """
    root = Path(get_local_root_dir()).resolve()
    parts = [p for p in s3_key.replace("\\", "/").split("/") if p and p != "."]
    if not parts:
        raise HTTPException(status_code=400, detail="Invalid storage key")
    if any(p == ".." for p in parts):
        raise HTTPException(status_code=400, detail="Invalid storage key")
    dest = root.joinpath(*parts).resolve()
    try:
        dest.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid storage key")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        dest.write_bytes(file_content)
    except OSError as e:
        logger.error(f"Error saving file under S3 key layout: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while saving the file."
        )
    return str(dest)


def delete_file_locally(file_path: str):
    """Delete file from local filesystem."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"File {file_path} deleted successfully")
        else:
            logger.warning(f"File {file_path} does not exist")
    except Exception as e:
        logger.error(f"Error deleting file locally: {e}")
        raise


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


class S3Upload_LocalFileVersion:

    @staticmethod
    async def upload_generate_image(
        file_name: str, file_content: bytes, file_extension: str, cat: FileCategory
    ):
        from app.services.s3_services import generate_s3key_for

        s3_key = generate_s3key_for(file_name, cat)
        content_type = (
            f"image/{file_extension}"
            if file_extension.lower() in ["jpg", "jpeg", "png", "gif"]
            else "application/octet-stream"
        )

        try:
            file_path = save_file_locally_under_s3_key(s3_key, file_content)
            file_url = f"file://{file_path}"
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

        if not content_type:
            _, ext = os.path.splitext(file_name)
            content_type = (
                f"image/{ext}"
                if ext.lower() in [".jpg", ".jpeg", ".png", ".gif"]
                else "application/octet-stream"
            )

        try:
            file_path = save_file_locally(file_name, file_content)

            file_url = f"file://{file_path}"
            print("File uploaded to: ", file_url)
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
    async def upload_file_context_extracted_image(
        file_name: str,
        file_content: bytes,
        file_context_id: str,
        file_id: str,
        content_type: str = None,
    ):
        if not content_type:
            _, ext = os.path.splitext(file_name)
            content_type = (
                f"image/{ext}"
                if ext.lower() in [".jpg", ".jpeg", ".png", ".gif"]
                else "application/octet-stream"
            )

        try:
            file_path = save_file_locally(file_name, file_content)

            file_url = f"file://{file_path}"
            print("File uploaded to: ", file_url)
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
        try:
            file_url = f"file://{local_file_path}"
            file_name = os.path.basename(local_file_path)
            await _FileServices.add_entry(
                file_url, content_type, file_name, FileCategory.UPLOAD
            )
            return file_url

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise HTTPException(
                status_code=500, detail="An error occurred while uploading the file."
            )

    @staticmethod
    async def safe_delete_file(file_url: str):
        try:
            # Expected format: file:///path/to/file.ext
            if file_url.startswith("file://"):
                file_path = file_url[7:]  # Remove 'file://' prefix
            else:
                file_path = file_url

            print(f"safe_delete_file: url={file_url} path={file_path}")

            delete_file_locally(file_path)
            await _FileServices.delete_entry(file_url)

            print(f"File {file_url} deleted successfully")
            return {"detail": "File deleted successfully."}
        except Exception as e:
            logger.error(f"An error occurred while deleting file: {e}")
            traceback.print_exc()
            # raise HTTPException(status_code=500, detail="An error occurred while deleting the file.")

    @staticmethod
    async def delete_if_owner(file_url: str):
        if not is_owner(file_url):
            raise HTTPException(status_code=401, detail=f"Not owner")
        await S3Upload_LocalFileVersion.safe_delete_file(file_url)
