# routes/user_project_routes.py
from typing import List

from fastapi import APIRouter, Response

from ..services.project_service import ProjectService
from ..models.user_project import UserProjectInDB, UserProjectBase

router = APIRouter()


@router.get("/user_projects", response_model=List[UserProjectInDB])
def get_all_user_projects():
    return ProjectService.get_all_user_projects()


@router.get("/user_projects/{user_project_id}")
def get_user_project_by_id(user_project_id):
    return ProjectService.get_user_project_by_id(user_project_id)


@router.post("/user_projects")
def create_user_project(user_project: UserProjectBase):
    ProjectService.add_user_project(user_project)
    return Response(status_code=200)


@router.put("/user_projects/{user_project_id}")
def update_user_project(user_project_id, user_project: UserProjectInDB):
    ProjectService.update_user_project(user_project_id, user_project)
    return Response(status_code=200)


@router.delete("/user_projects/{user_project_id}")
def delete_user_project(user_project_id):
    ProjectService.delete_user_project(user_project_id)
