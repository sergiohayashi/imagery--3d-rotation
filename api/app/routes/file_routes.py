from typing import List

from fastapi import APIRouter, Response
from pydantic import BaseModel
from starlette.responses import JSONResponse

from app.services.project_service_async import ProjectServiceAsync
from ..models import ProjectInDB, ProjectBase, ProjectWithRole
from ..models.role import Role
from ..services.file_services import FileServices
from ..services.project_service import ProjectService

router = APIRouter()


@router.get("/files")
async def get_files(
    project_id: str, category: str = "g", start: int = 0, size: int = 20
):
    return await FileServices.get_all_files(project_id, category, start, size)


@router.delete("/files/{id}")
async def delete_file_and_chat(id: str):
    return await FileServices.delete_file_and_chat(id)
