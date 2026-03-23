from typing import List

from fastapi import APIRouter, Response

from ..services.project_service import ProjectService
from ..services.user_service import UserService
from ..models.user import UserInDB, UserBase, ExternalUserAdd

router = APIRouter()


@router.get("/users", response_model=List[UserInDB])
def get_all_users():
    return UserService.get_all_users()


@router.get("/users/{user_id}")
def get_user_by_id(user_id):
    return UserService.get_user_by_id(user_id)


@router.post("/users", response_model=None)
def create_user(user: UserBase):
    UserService.create_user(user)
    return Response(status_code=200)


@router.put("/users/{user_id}")
def update_user(user_id, user: UserInDB):
    UserService.update_user(user_id, user)
    return Response(status_code=200)


@router.delete("/users/{user_id}")
def delete_user(user_id):
    UserService.delete_user(user_id)
    return Response(status_code=200)


@router.get("/users/{user_id}/projects")
def get_projects(user_id: str):
    return ProjectService.get_projects_by_user(user_id)


@router.post("/users/add-external", response_model=None)
async def create_external_user(user: ExternalUserAdd):
    UserService.create_external_user(user)
    return Response(status_code=200)
