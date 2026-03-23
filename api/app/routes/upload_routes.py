import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi import BackgroundTasks
import logging
import uuid
import re
from pydantic import BaseModel
from app.services.file_services import FileServices
from ..services.file_context_ingestor import FileContextIngestorService
from ..services.s3_services import FileCategory
from ..services.s3_services import (
    S3UploadServices,
    s3_client,
    UPLOAD_BUCKET_NAME,
    generate_s3key_for,
)

router = APIRouter()

logger = logging.getLogger(__name__)


def unique_filename_of(filename, content_type):
    if filename:
        # Split the filename into base and extension
        base, ext = os.path.splitext(filename)

        # Remove disallowed characters: anything except letters, numbers, underscore, and dot
        safe_base = re.sub(r"[^A-Za-z0-9_.]", "", base)

        # Generate a unique GUID (hexadecimal representation without dashes)
        unique_id = uuid.uuid4().hex

        # Concatenate the GUID to the original file name
        new_filename = f"{safe_base}_{unique_id}{ext}"
    else:
        new_filename = f"{uuid.uuid4().hex}.{content_type.split('/')[-1]}"
    return new_filename


class GenerateLinkParams(BaseModel):
    filename: Optional[str] = None
    content_type: str
    file_context_id: Optional[str] = None


@router.post("/upload/generate-upload-url")
def generate_s3_upload_link(args: GenerateLinkParams):
    bucket_name = UPLOAD_BUCKET_NAME
    try:
        s3_key = generate_s3key_for(
            unique_filename_of(args.filename, args.content_type),
            FileCategory.FILE_CONTEXT if args.file_context_id else FileCategory.UPLOAD,
            args.file_context_id,
        )
        pre_signed_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": s3_key,
                "ContentType": args.content_type,
            },
            HttpMethod="PUT",
            ExpiresIn=600,  # URL will expire in 10 minutes
        )
        print("pre_signed_url", pre_signed_url)
        return {
            "presigned_url": pre_signed_url,
            "s3_key": s3_key,
            "filename": args.filename
            or f"{uuid.uuid4().hex}.{args.content_type.split('/')[-1]}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Could not generate pre-signed URL: {str(e)}"
        )


class ConfirmUpload(BaseModel):
    filename: Optional[str] = None
    s3_key: str
    project_id: str
    chat_id: Optional[str] = None
    content_type: Optional[str] = None
    file_context_id: Optional[str] = None


@router.post("/upload/confirm-upload")
async def confirm_uploaded_file(
    payload: ConfirmUpload, background_tasks: BackgroundTasks
):
    # file_url = f"https://{UPLOAD_BUCKET_NAME}.s3.sa-east-1.amazonaws.com/{payload.s3_key}"
    file_url = (
        f"https://{UPLOAD_BUCKET_NAME}.s3.us-east-1.amazonaws.com/{payload.s3_key}"
    )
    file_id = await FileServices.add_entry(
        file_url,
        payload.content_type,
        payload.filename,
        FileCategory.FILE_CONTEXT if payload.file_context_id else FileCategory.UPLOAD,
        payload.project_id,
        payload.chat_id,
        payload.file_context_id,
    )

    if payload.file_context_id:
        # file ingestion running in background...
        print("ingest_file running in background...")
        background_tasks.add_task(FileContextIngestorService.ingest_file, file_id)
        print("ingest_file running in background...return right away.")

    return {"file_url": file_url}


@router.delete("/upload")
async def delete_uploaded_file(file_url):
    await S3UploadServices.delete_if_owner(file_url)
