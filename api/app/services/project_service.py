from ..models.project import ProjectInDB, ProjectBase, ProjectWithRole
from fastapi import HTTPException, status
from ..config.config import config
from typing import List
from bson import ObjectId
from pymongo.results import UpdateResult
from ..models.role import Role
from ..database import db
from ..models.user_project import UserProjectInDB, UserProjectBase


class ProjectService:

    @staticmethod
    def ensure_admin_permission_for(project_id):
        user_info = config.user_info_var.get()
        if not user_info["is_superuser"]:
            if not db.user_projects.find_one(
                {
                    "project_id": ObjectId(project_id),
                    "user_id": ObjectId(user_info["user_id"]),
                    "role": Role.admin,
                }
            ):
                raise HTTPException(
                    detail="Invalid user or without permission",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

    @staticmethod
    def is_last_admin_for(project_id, user_id):
        # get all admin users
        admin_users = list(
            db.user_projects.find(
                {"project_id": ObjectId(project_id), "role": "admin"}, {"user_id"}
            )
        )
        print("is_last_admin_for", "admin_users", admin_users)
        # more than 1, is ok
        if len(admin_users) != 1:
            return False

        # is the unique admin, the user I am searching?
        print(
            "is_last_admin_for",
            str(admin_users[0]["user_id"]),
            user_id,
            str(admin_users[0]["user_id"]) == user_id,
        )
        return str(admin_users[0]["user_id"]) == user_id

    @staticmethod
    def validate_role(role):
        # pydantic way to validate the role domain
        try:
            Role(role)
        except ValueError:
            raise ValueError('Role must be either "admin" or "contributor"')

    @staticmethod
    def get_project_by_id(id: str) -> ProjectInDB:
        project = db.projects.find_one({"_id": ObjectId(id)})
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return project

    @staticmethod
    def create_project(project: ProjectBase, user_id=None) -> ProjectInDB:
        if not user_id:
            user_id = config.user_info_var.get().get("user_id")

        # insert a new project
        new_project = db.projects.insert_one(project.dict())
        created_project = db.projects.find_one({"_id": new_project.inserted_id})

        # turn the user as admin
        from ..models.role import Role

        ProjectService.add_user_project(
            user_id, str(new_project.inserted_id), Role.admin
        )
        return created_project

    @staticmethod
    def get_projects_by_user_id(user_id: str) -> List[ProjectInDB]:
        user_project_relations = db.user_projects.find({"user_id": ObjectId(user_id)})
        if user_project_relations is None:
            return []
            # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No projects found for this user")

        projects = []
        for relation in user_project_relations:
            project = db.projects.find_one({"_id": relation["project_id"]})
            if project:
                projects.append(project)
        return projects

    @staticmethod
    def delete_project(project_id: str):
        # TODO: Fazer soft delete...
        ProjectService.ensure_admin_permission_for(project_id)
        db.user_projects.delete_many({"project": ObjectId(project_id)})
        # delete artifacts
        db.context_artifacts.delete_many({"project": ObjectId(project_id)})
        # TODO: delete system message
        # TODO: delete chat entry
        # TODO: delete chat
        # delete project
        db.projects.delete_one({"_id": ObjectId(project_id)})
        return True

    @staticmethod
    def update_project(project_id: str, project: ProjectBase):
        ProjectService.ensure_admin_permission_for(project_id)

        print(f"Update project {project_id} for name {project.name}")
        db.projects.update_one(
            {"_id": ObjectId(project_id)}, {"$set": {"name": project.name}}
        )

    @staticmethod
    def get_all_user_projects():
        return db.user_projects.find()

    @staticmethod
    def get_user_project_by_id(user_project_id):
        return db.user_projects.find_one({"_id": user_project_id})

    @staticmethod
    def add_user_project(user_id: str, project_id: str, role: str):
        ProjectService.validate_role(role)
        new_user_project = db.user_projects.insert_one(
            {
                "user_id": ObjectId(user_id),
                "project_id": ObjectId(project_id),
                "role": role,
            }
        )
        created_user_project = db.user_projects.find_one(
            {"_id": new_user_project.inserted_id}
        )
        return UserProjectInDB(**created_user_project)

    @staticmethod
    def update_user_project(user_project_id, user_project: UserProjectInDB):
        return db.user_projects.update_one(
            {"_id": user_project_id}, {"$set": user_project.dict(by_alias=True)}
        )

    @staticmethod
    def delete_user_project(project_id: str, user_id: str):
        ProjectService.ensure_admin_permission_for(project_id)

        if ProjectService.is_last_admin_for(project_id, user_id):
            raise HTTPException(
                detail="Last administrator user cannot be removed",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return db.user_projects.delete_one(
            {"user_id": ObjectId(user_id), "project_id": ObjectId(project_id)}
        )

    @staticmethod
    def create_or_update_role(project_id: str, user_id: str, role: str) -> UpdateResult:
        ProjectService.validate_role(role)
        if not db.users.find_one({"_id": ObjectId(user_id)}):
            raise HTTPException(
                detail="Invalid user id", status_code=status.HTTP_400_BAD_REQUEST
            )
        if not db.projects.find_one({"_id": ObjectId(project_id)}):
            raise HTTPException(
                detail="Invalid project id", status_code=status.HTTP_400_BAD_REQUEST
            )

        if role != "admin":
            if ProjectService.is_last_admin_for(project_id, user_id):
                raise HTTPException(
                    detail="Last administrator user cannot be removed or have their role modified",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        result = db.user_projects.update_one(
            {"user_id": ObjectId(user_id), "project_id": ObjectId(project_id)},
            {"$set": {"role": role}},
            upsert=True,
        )
        result.raw_result["upserted"] = (
            str(result.raw_result["upserted"])
            if "upserted" in result.raw_result
            else None
        )
        return result.raw_result

    @staticmethod
    def get_users_by_project(project_id: str) -> List[dict]:
        print("project_id", project_id)
        user_projects = db.user_projects.find(
            {"project_id": ObjectId(project_id)}, {"user_id": 1, "role": 1}
        )
        users = []
        for user_project in user_projects:
            print("user_project", user_project)
            print("user_project[useid]:", user_project["user_id"])
            user = db.users.find_one({"_id": user_project["user_id"]}, {"email": 1})
            if user:
                users.append(
                    {
                        "user_id": str(user_project["user_id"]),
                        "email": user["email"],
                        "role": user_project["role"],
                    }
                )
            else:
                print("Invalid user found in user_project: ", user_project["user_id"])
        return users

    @staticmethod
    def get_projects_by_user(user_id: str) -> List[dict]:
        user_projects = db.user_projects.find(
            {"user_id": ObjectId(user_id)}, {"project_id": 1, "role": 1}
        )
        projects = []
        for user_project in user_projects:
            project = db.projects.find_one(
                {"_id": user_project["project_id"]}, {"name": 1}
            )
            projects.append(
                {
                    "project_id": str(user_project["project_id"]),
                    "name": project["name"],
                    "role": user_project["role"],
                }
            )
        return projects

    @staticmethod
    def create_or_update_role_by_email(project_id, email_list, role):
        import re

        ProjectService.validate_role(role)
        not_found = []

        # Regular expression to match emails in different formats
        email_pattern = re.compile(r"[\w.-]+@[\w.-]+")
        emails = email_pattern.findall(email_list)

        for email in emails:
            email = email.strip()
            if email:
                user = db.users.find_one({"email": email.lower()})
                if user:
                    ProjectService.create_or_update_role(
                        project_id, str(user["_id"]), role
                    )
                else:
                    not_found.append(email)

        if not not_found:
            return status.HTTP_200_OK, "success"
        else:
            return (
                status.HTTP_207_MULTI_STATUS,
                "The following users were not found in the system: \n"
                + "\n".join(not_found),
            )
