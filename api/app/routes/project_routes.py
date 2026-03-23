from datetime import datetime
from typing import List

from fastapi import APIRouter, Response, Query, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.responses import JSONResponse

from app.services.project_service_async import ProjectServiceAsync
from ..models import ProjectInDB, ProjectBase, ProjectWithRole
from ..models.role import Role
from ..services.chat_exporter import count_chat, export_chat
from ..services.project_service import ProjectService

router = APIRouter()


class EmailRole(BaseModel):
    email_list: str
    role: str


@router.get("/projects", response_model=List[ProjectWithRole])
async def get_projects():
    return await ProjectServiceAsync.get_all_projects_async()


@router.get("/projects/{project_id}", response_model=ProjectInDB)
def get_project(project_id: str):
    return ProjectService.get_project_by_id(project_id)


@router.post("/projects", response_model=ProjectInDB)
def create_project(project: ProjectBase):
    ProjectService.create_project(project)
    return Response(status_code=200)


@router.post("/projects/{project_id}/users")
def create_or_update_project_user_by_email(project_id: str, email_role: EmailRole):
    print("/projects/project_id/users called!")
    status_code, content = ProjectService.create_or_update_role_by_email(
        project_id, email_role.email_list, email_role.role
    )
    return JSONResponse(status_code=status_code, content=content)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    ProjectService.delete_project(project_id)
    return Response(status_code=200)


@router.get("/projects/{project_id}")
def delete_project(project_id: str):
    ProjectService.get_user_project_by_id(project_id)
    return Response(status_code=200)


@router.put("/projects/{project_id}")
def update_project(project_id: str, project: ProjectBase):
    ProjectService.update_project(project_id, project)
    return Response(status_code=200)


@router.post("/projects/{project_id}/users/{user_id}")
def create_or_update_project_user(project_id: str, user_id: str, role: Role):
    ProjectService.create_or_update_role(project_id, user_id, role.role)
    return Response(status_code=200)


@router.delete("/projects/{project_id}/users/{user_id}")
def delete_user_project(project_id: str, user_id: str):
    ProjectService.delete_user_project(project_id, user_id)
    return Response(status_code=200)


@router.get("/projects/{project_id}/users")
def get_project_users(project_id: str) -> List[dict]:
    return ProjectService.get_users_by_project(project_id)


@router.get("/projects/{project_id}/chat-export")
async def export_chats(
    project_id: str,
    background_tasks: BackgroundTasks,
    year: int = Query(..., description="Year"),
    # db=Depends(get_db),
    # current_user: User = Depends(...),  # your auth dependency
):
    response: FileResponse = await export_chat(project_id, year, background_tasks)
    return response


@router.get("/projects/{project_id}/chat-count")
async def count_chats(
    project_id: str,
    year: int = Query(..., description="Year"),
    # db=Depends(get_db),
    # current_user: User = Depends(...),  # your auth dependency
):
    response: int = await count_chat(
        project_id,
        year,
    )
    return JSONResponse(status_code=200, content={"count": response})
