import datetime
import json
import os
import mimetypes
import uuid
from pathlib import Path

import re
import unicodedata
from urllib.parse import urlparse, urlunparse

from bson import ObjectId


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)  # Convert ObjectId to string
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()  # Convert datetime to ISO format string
        # Add more custom serialization logic here if needed
        return super().default(obj)


def to_url_valid_filename(filename: str) -> str:
    """
    Convert a filename to a valid format that can be used as part of a URL.

    Args:
        filename: The original filename string

    Returns:
        A URL-safe filename string
    """
    # Separate the extension if present
    if "." in filename:
        name, ext = filename.rsplit(".", 1)
        has_extension = True
    else:
        name = filename
        ext = ""
        has_extension = False

    # Normalize unicode characters (convert accented chars to ASCII equivalents)
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    name = name.lower()

    # Replace spaces and underscores with hyphens
    name = re.sub(r"[\s_]+", "-", name)

    # Remove any character that's not alphanumeric, hyphen, or dot
    name = re.sub(r"[^a-z0-9\-]", "", name)

    # Replace multiple consecutive hyphens with a single hyphen
    name = re.sub(r"-+", "-", name)

    # Remove leading and trailing hyphens
    name = name.strip("-")

    # Handle the extension
    if has_extension:
        ext = ext.lower()
        ext = re.sub(r"[^a-z0-9]", "", ext)
        if ext:
            return f"{name}.{ext}"

    return name


def get_filename(file_fullpath):
    # Normalize path separators to the current OS's default
    normalized_path = file_fullpath.replace("\\", os.sep).replace("/", os.sep)
    return Path(normalized_path).name


def guess_content_type_from_filename(file_name: str) -> str:
    if not file_name:
        return "application/octet-stream"

    # 1)  Let the standard library try first
    mime, _ = mimetypes.guess_type(file_name)
    if mime:
        return mime

    # 2)  Our own (extendable) mapping
    _, ext = os.path.splitext(file_name)
    ext = ext.lower().lstrip(".")  # `".JPG" -> "jpg"`

    custom_map = {
        # Images
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "svg": "image/svg+xml",
        "tif": "image/tiff",
        "tiff": "image/tiff",
        # Text-ish
        "txt": "text/plain",
        "csv": "text/csv",
        "html": "text/html",
        "htm": "text/html",
        "json": "application/json",
        "xml": "application/xml",
        "yaml": "application/x-yaml",
        "yml": "application/x-yaml",
        # Documents
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ppt": "application/vnd.ms-powerpoint",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        # Archives / compressed
        "zip": "application/zip",
        "gz": "application/gzip",
        "tar": "application/x-tar",
        "7z": "application/x-7z-compressed",
        # Audio / Video
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "ogg": "audio/ogg",
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "avi": "video/x-msvideo",
        "mkv": "video/x-matroska",
    }

    return custom_map.get(ext, "application/octet-stream")


def add_uuid_to_filename(path_or_url: str) -> str:
    # generate 48-bit randomness (12 hex chars)
    code = uuid.uuid4().hex[-12:]

    parsed = urlparse(path_or_url)

    if parsed.scheme and parsed.scheme != "file":
        # It's an http/https URL or similar
        dirname, filename = os.path.split(parsed.path)
        name, ext = os.path.splitext(filename)
        new_filename = f"{name}-{code}{ext}"
        new_path = os.path.join(dirname, new_filename)
        parsed = parsed._replace(path=new_path)
        return urlunparse(parsed)
    else:
        # It's a file path or file:// URL
        if parsed.scheme == "file":
            path = parsed.path
        else:
            path = path_or_url

        dirname, filename = os.path.split(path)
        name, ext = os.path.splitext(filename)
        new_filename = f"{name}-{code}{ext}"
        new_path = os.path.join(dirname, new_filename)

        if parsed.scheme == "file":
            return f"file://{new_path}"
        else:
            return new_path


# --- Example usage ---
# print(add_uuid_to_filename("file:///tmp/file1.png"))
# print(add_uuid_to_filename("/home/user/image.jpg"))
# print(add_uuid_to_filename("https://example.com/pic.png"))
