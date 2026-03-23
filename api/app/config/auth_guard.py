from bson import ObjectId
from fastapi import HTTPException
from starlette import status

from app.config.config import config
from app.database import db


class AuthzGuards:
    pass


def for_project(project_id):
    # check if the current user has access to the project
    user_info = config.user_info_var.get()
    if not user_info:
        print("User not found!")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if user_info["is_superuser"]:
        return  # OK

    exists = (
        db.user_projects.find_one(
            {
                "user_id": ObjectId(user_info["user_id"]),
                "project_id": ObjectId(project_id),
            },
            {"_id": 1},
        )
        is not None
    )
    if not exists:
        print(f'User {user_info["user_id"]} has not access to project {project_id}')
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # passed!
