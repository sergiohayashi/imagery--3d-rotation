# services/user_service.py
from bson import ObjectId

from ..config import custom_auth
from ..models import ProjectBase
from .project_service import ProjectService
from ..database import db
from ..models.user import UserInDB, UserBase
from ..config.config import config
from fastapi import HTTPException, status


class UserService:
    @staticmethod
    def get_all_users():
        return db.users.find()

    @staticmethod
    def get_user_by_id(user_id):
        return db.users.find_one({"_id": user_id})

    @staticmethod
    def create_user(user: UserBase) -> UserInDB:
        new_user = db.users.insert_one(user.model_dump(by_alias=True))
        created_user = db.users.find_one({"_id": new_user.inserted_id})
        return UserInDB(**created_user)

    @staticmethod
    def update_user(user_id, user: UserBase):
        return db.users.update_one({"_id": user_id}, {"$set": user.dict(by_alias=True)})

    @staticmethod
    def delete_user(user_id):
        return db.users.delete_one({"_id": user_id})

    @staticmethod
    def get_user_by_email(email):
        return db.users.find_one({"email": email.lower()})

    @classmethod
    def register(cls, email, name, tenant_id):
        email = email.lower()
        user = db.users.find_one({"email": email})
        if not user:
            # first time, register
            user_id = db.users.insert_one(
                {"name": name, "email": email, "tenantId": tenant_id}
            ).inserted_id
        else:
            # existing user. Check if continues valid. When the active field don't exist assume valid.
            if not user.get("active", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive",
                )
            user_id = user["_id"]
            name = user["name"]

        if not db.user_projects.find_one({"user_id": user_id}):
            ProjectService.create_project(
                ProjectBase(name=f"{name.split()[0]}'s workspace"), str(user_id)
            )
            print(f"Added new user {email} to database.")

        return {
            "name": name,
            "email": email,
            "tenant_id": tenant_id,
            "tenant_name": config.tenants.get(tenant_id, {}).get("name"),
            "permissions": ["manager"] if email in config.managers else [],
        }

    @classmethod
    def get_current_user(cls):
        user_id = config.user_info_var.get()["user_id"]
        user = db.users.find_one({"_id": ObjectId(user_id)})
        return user_id, user["email"]

    @classmethod
    def get_cached_name(cls, cache, id: ObjectId):
        if id not in cache:
            cache[id] = db.users.find_one({"_id": id})
        return cache.get(id).get("name").split()[0]

    @classmethod
    def update_password(cls, password: str):
        user_id = config.user_info_var.get()["user_id"]
        user = db.users.find_one({"_id": ObjectId(user_id)})
        # should not happen, but extra protection
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        db.users.update_one(
            {
                "_id": user["_id"],
            },
            {"$set": {"hashed_password": custom_auth.hash_password(password)}},
        )

    @classmethod
    def verify_user_and_password(cls, email: str, password: str):
        user = db.users.find_one({"email": email.lower()})
        if not user:
            print("User not found!")
            return None
        tenant_id = user.get("tenantId")
        if custom_auth.verify_password(password, user.get("hashed_password")):
            return {
                "name": user.get("name"),
                "email": user.get("email"),
                "tenant_id": tenant_id,
            }
        else:
            print("Password not match!")
            return None
