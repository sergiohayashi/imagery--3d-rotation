from typing import List

from bson import ObjectId

from app.database_async import db_async
from ..config.config import config
from ..models.project import ProjectWithRole


class ProjectServiceAsync:
    @staticmethod
    async def get_all_projects_async() -> List[ProjectWithRole]:
        user_info = config.user_info_var.get()
        if user_info["is_superuser"]:
            projects_in_db = db_async.projects.find()
            projects = [
                ProjectWithRole(
                    name=project["name"],
                    description=project["description"],
                    id=str(project["_id"]),
                    role="su",
                )
                async for project in projects_in_db
            ]
            # return projects
        else:
            user_project_relations = db_async.user_projects.find(
                {"user_id": ObjectId(user_info["user_id"])}
            )
            # if user_project_relations is None:
            #     return []

            projects = []
            async for relation in user_project_relations:
                project = await db_async.projects.find_one(
                    {"_id": relation["project_id"]}
                )
                if project:
                    projects.append(
                        ProjectWithRole(
                            name=project["name"],
                            description=project["description"],
                            id=str(project["_id"]),
                            role=relation["role"],
                        )
                    )

        projects.sort(key=lambda p: p.name.lower())
        return projects
