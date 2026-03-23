# services/chat_service.py
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException
from pymongo import DESCENDING
from starlette import status

from .s3_services import S3UploadServices
from ..config.config import config
from ..database import db
from ..llm_services.any_model import AnyModel
from ..models.chat import ChatBase, ChatInDB, ChatWithContent, ChatEntriesForSelection


class ChatService:
    @staticmethod
    def create_chat(chat: ChatBase) -> ChatInDB:
        chat_dict = chat.model_dump(by_alias=True)
        chat_dict["startTime"] = datetime.now(timezone.utc)
        chat_id = db.chats.insert_one(chat_dict).inserted_id
        return ChatInDB(**db.chats.find_one({"_id": chat_id}))

    @staticmethod
    def get_all_chats(project_id: str) -> list[ChatInDB]:
        if not project_id:
            return []
        chats = db.chats.find({"project": ObjectId(project_id)})
        return [ChatInDB(**chat) for chat in chats]

    @staticmethod
    def get_chat_by_id(chat_id: str) -> ChatInDB:
        chat = db.chats.find_one({"_id": chat_id})
        if chat:
            return ChatInDB(**chat)
        else:
            return None

    @staticmethod
    def get_latest_chats_with_intro(
        project_id: str, selected_chat_id: str = None, last_id: str = None
    ) -> list[ChatWithContent]:
        if not project_id:
            return []
        user_id = config.user_info_var.get().get("user_id")

        last = db.chats.find_one({"_id": ObjectId(last_id)}) if last_id else None

        latest_chats = (
            list(
                db.chats.find(
                    {
                        "project_id": ObjectId(project_id),
                        "updated_at": {"$lt": last["updated_at"]},
                    }
                )
                .sort("updated_at", DESCENDING)
                .limit(50)
            )
            if last
            else list(
                db.chats.find({"project_id": ObjectId(project_id)})
                .sort("updated_at", DESCENDING)
                .limit(30)
            )
        )

        # Check if the specific document is in the latest chats
        if selected_chat_id:
            if not any(
                chat["_id"] == ObjectId(selected_chat_id) for chat in latest_chats
            ):
                # If not, query for the specific document
                specific_chat = db.chats.find_one({"_id": ObjectId(selected_chat_id)})
                # Add the specific chat at the beginning of the list
                if specific_chat:
                    latest_chats = [specific_chat] + latest_chats
        chats = latest_chats

        chat_with_intro_list = []
        for chat in chats:
            chat_id = chat["_id"]
            chat_with_intro = ChatWithContent(
                id=str(chat_id),
                startTime=chat["created_at"],
                endTime=chat.get("updated_at"),
                title=chat.get("title") or "(no name)",
            )
            owner = db.users.find_one({"_id": chat.get("user_id")})
            if owner:
                chat_with_intro.owner = owner.get("name")
            chat_with_intro.isOwner = chat.get("user_id") == ObjectId(user_id)
            chat_with_intro_list.append(chat_with_intro)
        return chat_with_intro_list

    @staticmethod
    def search_recent_public_chats():
        limit = 10
        limit_date = datetime.now(timezone.utc) - timedelta(days=3)
        query = {"public_at": {"$gte": limit_date}}
        chats = list(db.chats.find(query).sort("public_at", -1))
        # random_chats = random.sample(chats, min(limit, len(chats)))

        result = [
            {
                "id": str(chat["_id"]),
                "title": chat.get("title"),
                "view_count": chat.get("view_count"),
            }
            for chat in chats
        ]
        return result

    @staticmethod
    def get_chat_thread_public(chat_id) -> dict:
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        user_id = config.user_info_var.get().get("user_id")
        if chat.get("public_at") is None:
            raise HTTPException(
                detail="Not public.", status_code=status.HTTP_400_BAD_REQUEST
            )

        entries = db.chat_entries.find(
            {"chat_id": ObjectId(chat_id)}, sort=[("created_at", 1)]
        )
        entries_list = []
        for entry in entries:
            entries_list.append(
                {
                    "role": entry.get("role"),
                    "content": entry.get("content"),
                    "image_url": entry.get("image_url"),
                    "file_url": entry.get("file_url"),
                    "file_name": entry.get("file_name"),
                    "content_type": entry.get("content_type"),
                    "meta": (
                        {
                            "model": entry["meta"].get("model"),
                            "company": entry["meta"].get("company"),
                        }
                        if entry.get("meta")
                        else None
                    ),
                }
            )

        result = {
            "title": chat["title"],
            "entries": entries_list,
        }

        db.chat_view.update_one(
            # filter_criteria
            {"user_id": ObjectId(user_id), "chat_id": ObjectId(chat_id)},
            # new_document,
            {
                "$setOnInsert": {
                    "user_id": ObjectId(user_id),
                    "chat_id": ObjectId(chat_id),
                }
            },
            upsert=True,
        )

        view_count = db.chat_view.count_documents({"chat_id": ObjectId(chat_id)})
        db.chats.update_one(
            {"_id": ObjectId(chat_id)}, {"$set": {"view_count": view_count}}
        )
        return result

    @classmethod
    def selective_duplicate(cls, chat_id, title, entries_id):
        user_id = config.user_info_var.get().get("user_id")

        # load the chat
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        entries_id = [ObjectId(id) for id in entries_id]
        entries = db.chat_entries.find(
            {
                "chat_id": ObjectId(chat_id),
                "_id": {"$in": entries_id},
            }
        ).sort("created_at", DESCENDING)

        # generate chat
        new_chat = {
            key: value
            for (key, value) in chat.items()
            if key not in ["_id", "user_id", "title", "estimate_total_cost"]
        }
        new_chat["user_id"] = ObjectId(user_id)
        new_chat["title"] = title or "Copy of " + (chat.get("title") or "(no title)")
        new_chat["created_at"] = datetime.now(timezone.utc)
        new_chat["updated_at"] = datetime.now(timezone.utc)
        new_chat_id = db.chats.insert_one(new_chat).inserted_id

        # copy entries
        for e in entries:
            new_e = {
                key: value
                for (key, value) in e.items()
                if key not in ["_id", "chat_id"]
            }
            new_e["chat_id"] = new_chat_id
            db.chat_entries.insert_one(new_e)

        return str(new_chat_id)

    @staticmethod
    def update_title_async(chat_id, user_message):

        async def update_title():
            # generate title
            title, _ = await AnyModel().generate_title(user_message)

            # update the chat register with the generated title. limit to 80 chars
            db.chats.update_one(
                {"_id": ObjectId(chat_id) if isinstance(chat_id, str) else chat_id},
                {
                    "$set": {
                        "title": title[:80],
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

        asyncio.create_task(update_title())

    @staticmethod
    async def create_continuation(chat_id):
        # get user info
        user_id = config.user_info_var.get().get("user_id")

        # load current chat
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        system_messages = db.chat_entries.find(
            {"chat_id": ObjectId(chat_id), "role": "system"}
        )
        user_entries = db.chat_entries.find(
            {"chat_id": ObjectId(chat_id), "role": "user"}, {"content": 1, "_id": 0}
        ).sort(
            "created_at", 1
        )  # ascending

        # generate summary context
        context, meta = await AnyModel().generate_conversation_context(
            [c["content"] for c in user_entries]
        )

        new_chat = {
            key: value
            for (key, value) in chat.items()
            if key not in ["_id", "user_id", "title", "estimate_total_cost"]
        }
        new_chat["user_id"] = ObjectId(user_id)
        new_chat["title"] = "Cont. of " + (chat.get("title") or "(no title)")
        new_chat["created_at"] = datetime.now(timezone.utc)
        new_chat["updated_at"] = datetime.now(timezone.utc)
        new_chat_id = db.chats.insert_one(new_chat).inserted_id

        for e in system_messages:
            new_e = {
                key: value
                for (key, value) in e.items()
                if key not in ["_id", "chat_id"]
            }
            new_e["chat_id"] = new_chat_id
            db.chat_entries.insert_one(new_e)

        # insert context
        db.chat_entries.insert_one(
            {
                "chat_id": new_chat_id,
                "role": "user",
                "meta": meta if type(meta) == dict else meta.model_dump(),
                "created_at": datetime.now(timezone.utc),
                "user_id": ObjectId(user_id),
                "project_id": chat.get("project_id"),
                "content": f"{context}",
            }
        )

        # generate new title
        ChatService.update_title_async(new_chat_id, context)

        return str(new_chat_id)

    @staticmethod
    def rename(chat_id, title):
        # get user info
        user_id = config.user_info_var.get().get("user_id")

        # load current chat
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        if chat["user_id"] != ObjectId(user_id):
            raise HTTPException(
                detail="Not owner.", status_code=status.HTTP_400_BAD_REQUEST
            )

        # make the update
        db.chats.update_one({"_id": chat.get("_id")}, {"$set": {"title": title}})

    @staticmethod
    async def delete(chat_id):
        user_id = config.user_info_var.get().get("user_id")
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        if not chat:
            return
        if chat["user_id"] != ObjectId(user_id):
            raise HTTPException(
                detail="Not owner.", status_code=status.HTTP_400_BAD_REQUEST
            )

        # delete images
        entries = db.chat_entries.find({"chat_id": chat["_id"]})
        for e in entries:
            if e.get("image_url"):
                await S3UploadServices.safe_delete_file(e.get("image_url"))
            if e.get("file_url"):
                await S3UploadServices.safe_delete_file(e.get("file_url"))
            for out in e.get("output", []) or []:
                if out.get("file_url"):
                    await S3UploadServices.safe_delete_file(out.get("file_url"))

        # delete entries
        db.chat_entries.delete_many({"chat_id": chat["_id"]})
        db.chats.delete_many({"_id": chat["_id"]})

    @classmethod
    async def delete_entry(cls, chat_id, entry_id):
        user_id = config.user_info_var.get().get("user_id")
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        if chat["user_id"] != ObjectId(user_id):
            raise HTTPException(
                detail="Not owner.", status_code=status.HTTP_400_BAD_REQUEST
            )

        e = db.chat_entries.find_one({"_id": ObjectId(entry_id)})
        if not e:
            return
        if e.get("image_url"):
            await S3UploadServices.safe_delete_file(e.get("image_url"))
        if e.get("file_url"):
            await S3UploadServices.safe_delete_file(e.get("file_url"))

        for output in e.get("output", None) or []:
            if output.get("file_url"):
                await S3UploadServices.safe_delete_file(output.get("file_url"))

        # if there are alternatives, and entry is the main (is_alternative==0), then promote the next to main
        if e.get("is_alternative") == 0:
            alternatives = list(
                db.chat_entries.find(
                    {
                        "chat_id": e.get("chat_id"),
                        "created_at": e.get("created_at"),
                        "is_alternative": {"$ne": 0},
                    }
                )
            )
            if len(alternatives) > 0:
                db.chat_entries.update_one(
                    {"_id": alternatives[0]["_id"]}, {"$set": {"is_alternative": 0}}
                )
        db.chat_entries.delete_one({"_id": ObjectId(entry_id)})

    @classmethod
    def make_shared(cls, chat_id):
        user_id = config.user_info_var.get().get("user_id")
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        if chat["user_id"] != ObjectId(user_id):
            raise HTTPException(
                detail="Not owner.", status_code=status.HTTP_400_BAD_REQUEST
            )

        # make public (overwrite if already shared)
        shared_id = str(uuid4())
        db.chats.update_one(
            {"_id": ObjectId(chat_id)},
            {
                "$set": {
                    "shared_id": shared_id,
                    "shared_id_expire_date": datetime.now(timezone.utc)
                    + timedelta(days=30),
                }
            },
        )
        return shared_id

    @staticmethod
    def toggle_public(chat_id):
        user_id = config.user_info_var.get().get("user_id")
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        if chat["user_id"] != ObjectId(user_id):
            raise HTTPException(
                detail="Not owner.", status_code=status.HTTP_400_BAD_REQUEST
            )

        public_at = (
            datetime.now(timezone.utc) if chat.get("public_at", None) is None else None
        )

        db.chats.update_one(
            {"_id": ObjectId(chat_id)}, {"$set": {"public_at": public_at}}
        )
        return public_at

    # @classmethod
    # def get_chat_entries_for_selection(cls, chat_id):
    #     # user not validated, but assume that if the user knows the guid than has access
    #     # user_id = config.user_info_var.get().get('user_id')
    #     # chat = db.chats.find_one({"_id": ObjectId(chat_id)})
    #     entries = db.chat_entries.find(
    #         {
    #             "chat_id": ObjectId(chat_id),
    #             "$or": [
    #                 {"is_alternative": {"$exists": False}},  # field not present
    #                 {"is_alternative": 0}                    # present and equal to 0
    #             ],
    #         }, sort=[("created_at", 1)])
    #     entries_list = []
    #     for entry in entries:
    #         entries_list.append(ChatEntriesForSelection(
    #             role=entry.get("role"),
    #             content=entry.get("content")[:100] + "..." if entry.get("content") and len(
    #                 entry.get("content")) > 100 else entry.get("content"),
    #             image_url=entry.get("image_url"),
    #             file_url=entry.get("file_url"),
    #             entry_id=str(entry.get("_id")),
    #         ))
    #
    #     return entries_list

    @classmethod
    def get_new_id(cls):
        return str(ObjectId())

    @classmethod
    async def make_alternative_main(cls, chat_id, entry_id):
        user_id = config.user_info_var.get().get("user_id")
        chat = db.chats.find_one({"_id": ObjectId(chat_id)})
        if chat["user_id"] != ObjectId(user_id):
            raise HTTPException(
                detail="Not owner.", status_code=status.HTTP_400_BAD_REQUEST
            )

        # get the current entry
        entry = db.chat_entries.find_one({"_id": ObjectId(entry_id)})

        # get the main entry (alternative=0)
        main_entry = db.chat_entries.find_one(
            {
                "chat_id": entry.get("chat_id"),
                "created_at": entry.get("created_at"),
                "$or": [
                    {"is_alternative": {"$exists": False}},  # field not present
                    {"is_alternative": 0},  # present and equal to 0
                ],
            }
        )

        # switch the alternative number, and save
        db.chat_entries.update_one(
            {"_id": entry.get("_id")}, {"$set": {"is_alternative": 0}}
        )
        db.chat_entries.update_one(
            {"_id": main_entry.get("_id")},
            {"$set": {"is_alternative": entry.get("is_alternative")}},
        )
