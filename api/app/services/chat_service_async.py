import datetime
import re

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ASCENDING
from starlette import status

from app.database_async import db_async
from app.utils.local_file_url import file_url_to_mounted_url, rewrite_output_file_urls
from ..config.config import config
from ..models.chat import ChatWithTitle, ChatUserEntry


# from ..models.chat_message import ModelWithParameters


class ChatServiceAsync:

    @staticmethod
    async def init_empty_chat(project_id):
        context = config.user_info_var.get()
        now = datetime.datetime.now(datetime.timezone.utc)
        new_id = await db_async.chats.insert_one(
            {
                "project_id": ObjectId(project_id),
                "user_id": ObjectId(context.get("user_id")),
                "created_at": now,
                "updated_at": now,
                "estimate_total_cost": 0.0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "title": "(no name)",  # initially save with empty title
            }
        )
        return str(new_id.inserted_id)

    @staticmethod
    async def search_chat_titles_async(
        project_id,
        q,
        last_id,
        is_bookmarked,
        selected_chat_id,
        file_context_id: str = None,
    ):
        user_id = config.user_info_var.get().get("user_id")
        limit = 50

        # if bookmarked, use bookmark list as filter. Assuming bookmark list is not big
        if is_bookmarked:
            bookmark_chat_id_list = [
                x["chat_id"]
                async for x in db_async.bookmarks.find(
                    {"user_id": ObjectId(user_id)}, {"chat_id": 1, "_id": 0}
                )
            ]
        else:
            bookmark_chat_id_list = []

        last = (
            await db_async.chats.find_one({"_id": ObjectId(last_id)})
            if last_id
            else None
        )

        # case query is specified
        if q:
            query = {
                "title": {"$regex": f"{re.escape(q)}", "$options": "i"},
                # "$text": {"$search": q},
                "project_id": ObjectId(project_id),
                # "user_id": ObjectId(user_id)
            }

            # If there are bookmarks, add a condition to filter by chat_id
            if is_bookmarked:
                query["_id"] = {"$in": bookmark_chat_id_list}

            if last:
                query["updated_at"] = {"$lt": last["updated_at"]}

            if file_context_id:
                query["file_context_id"] = ObjectId(file_context_id)

            print("query: ", query)

            chats = (
                await db_async.chats.find(query)
                # await db_async.chats.find(query, {"score": {"$meta": "textScore"}})
                .sort("updated_at", -1).to_list(limit)
            )

        # otherwise (no query)
        else:
            query = {
                "project_id": ObjectId(project_id),
                # "user_id": ObjectId(user_id)
            }

            # If there are bookmarks, add a condition to filter by chat_id
            if is_bookmarked:
                query["_id"] = {"$in": bookmark_chat_id_list}

            if last:
                query["updated_at"] = {"$lt": last["updated_at"]}

            if file_context_id:
                query["file_context_id"] = ObjectId(file_context_id)

            print("query: ", query)

            chats = (
                await db_async.chats.find(
                    query,
                )
                .sort("updated_at", -1)
                .to_list(limit)
            )

            if selected_chat_id and not last:
                if not any(chat["_id"] == ObjectId(selected_chat_id) for chat in chats):
                    # If not, query for the specific document
                    specific_chat = await db_async.chats.find_one(
                        {"_id": ObjectId(selected_chat_id)}
                    )
                    # Add the specific chat at the beginning of the list
                    if specific_chat:
                        chats = [specific_chat] + chats

        # find bookmarks
        bookmarks = await db_async.bookmarks.find(
            {
                "user_id": ObjectId(user_id),
                "chat_id": {"$in": [chat["_id"] for chat in chats]},
            }
        ).to_list(None)
        bookmarks_set = {b["chat_id"] for b in bookmarks}

        # augment data
        result = []
        for chat in chats:
            chat_id = chat["_id"]
            # is_bookmarked = await db_async.bookmarks.find_one({"user_id": ObjectId(user_id), "chat_id": chat_id})
            # is_bookmarked = chat_id in bookmarks_set
            result.append(
                ChatWithTitle(
                    id=str(chat_id),
                    startTime=chat["created_at"],
                    endTime=chat.get("updated_at"),
                    title=chat.get("title") or "(no name)",
                    branch_model=chat.get("branch_model"),
                    is_bookmarked=chat_id in bookmarks_set,
                )
            )
            if chat.get("user_id") != ObjectId(user_id):
                owner = await db_async.users.find_one({"_id": chat.get("user_id")})
                if owner:
                    result[-1].owner = owner.get("name")
                result[-1].isOwner = False
            else:
                result[-1].isOwner = True

        return {
            "is_all": len(chats) < limit,
            "list": result,
            "project_id": project_id,
        }

    @staticmethod
    async def get_chat_thread_async(chat_id, skip=0):
        user_id = config.user_info_var.get().get("user_id")
        chat = await db_async.chats.find_one({"_id": ObjectId(chat_id)})
        if not chat:
            return {
                "id": chat_id,
                "entries": [],
                "skip": 0,
                "isOwner": True,
                "exists": False,
                "created_at": None,
            }
        entries = await db_async.chat_entries.find(
            {"chat_id": ObjectId(chat_id)},
            sort=[("created_at", 1), ("is_alternative", 1)],
        ).to_list()
        entries_list = []
        for entry in entries:
            # if entry.get("augmented_message_log_id"):
            #     augmented = await db_async.augmented_message_log.find_one({"_id": entry.get("augmented_message_log_id")})
            # else:
            augmented = None
            new_entry = ChatUserEntry(
                role=entry.get("role"),
                content=entry.get("content"),
                image_url=file_url_to_mounted_url(entry.get("image_url")),
                file_url=file_url_to_mounted_url(entry.get("file_url")),
                file_name=entry.get("file_name"),
                content_type=entry.get("content_type"),
                entry_id=str(entry.get("_id")),
                created_at=entry.get("created_at"),
                is_alternative=entry.get("is_alternative", 0),
                meta=(
                    {
                        "model": entry["meta"].get("model"),
                        "estimate_price": entry["meta"].get("estimate_price"),
                        "elapsed_in_sec": entry["meta"].get("elapsed_in_sec"),
                        "usage": entry["meta"].get("usage")
                        or entry["meta"].get("usage_metadata"),
                        "company": entry["meta"].get("company"),
                        "grounding_list": entry["meta"].get("grounding_list"),
                    }
                    if entry.get("meta")
                    else None
                ),
                # augmented_message_log_id=None,
                # offset=None,
                # agent_action_id=None,
                output=rewrite_output_file_urls(entry.get("output")),
            )
            if (
                new_entry.is_alternative > 0
                and len(entries_list) > 0
                and len(entries_list[-1]) > 0
                and entries_list[-1][0].created_at == new_entry.created_at
            ):
                entries_list[-1].append(new_entry)
            else:
                entries_list.append([new_entry])

        is_bookmarked = bool(
            await db_async.bookmarks.find_one(
                {"user_id": ObjectId(user_id), "chat_id": chat.get("_id")}
            )
        )
        result = dict(
            id=chat_id,
            project_id=str(chat["project_id"]),
            isOwner=(chat["user_id"] == ObjectId(user_id)),
            title=chat["title"],
            estimate_total_cost=round(chat.get("estimate_total_cost", 0.0), 4),
            total_input_tokens=chat.get("total_input_tokens", 0),
            total_output_tokens=chat.get("total_output_tokens", 0),
            entries=entries_list if skip == 0 else entries_list[skip:],
            is_bookmarked=is_bookmarked,
            public_at=chat.get("public_at"),
            created_at=chat.get("created_at"),
            skip=skip,
        )

        return result

    @staticmethod
    async def search_chat(project_id: str, query: str = None):

        limit = 300

        if not project_id:
            return []
        if not query or len(query) <= 1:
            return []
        # searc limited to current user entries
        user_id = config.user_info_var.get().get("user_id")

        # find in title
        chats = (
            await db_async.chats.find(
                {
                    # "title": Regex(query, 'i'),
                    "$text": {"$search": query},
                    "project_id": ObjectId(project_id),
                    # "user_id": ObjectId(user_id),
                },
                {"score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"}), ("created_at", -1)])
            .to_list(limit)
        )

        # find in chat text
        chat_entries = (
            await db_async.chat_entries.find(
                {
                    # "content": Regex(query, 'i'),
                    "$text": {"$search": query},
                    "project_id": ObjectId(project_id),
                    # "user_id": ObjectId(user_id),
                },
                {"score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"}), ("created_at", -1)])
            .to_list(limit)
        )

        # compose title with content
        chat_map = {str(chat["_id"]): [chat, []] for chat in chats}

        # sort entries by ascending datetime
        # chat_entries = list(chat_entries)
        chat_entries.sort(key=lambda x: x["created_at"])
        # pattern = re.compile(query, re.IGNORECASE)
        for entry in chat_entries:
            if not str(entry["chat_id"]) in chat_map:
                chat = await db_async.chats.find_one({"_id": entry["chat_id"]})
                if not chat:
                    continue
                # TODO: talvez nao precise..
                if chat["project_id"] != ObjectId(project_id):
                    continue
                chat_map[str(entry["chat_id"])] = [chat, []]

            if not chat_map[str(entry["chat_id"])][1]:  # use the first only..
                chat_map[str(entry["chat_id"])][1].append(entry["content"][:200])

        # generate final data
        result = [
            {
                "id": key,
                "title": value[0]["title"],
                "startTime": value[0]["created_at"],
                "content": "\n\n".join(value[1]),
            }
            for key, value in chat_map.items()
        ]
        result.sort(key=lambda x: x["startTime"], reverse=True)
        print("found: ", len(result))
        return result

    # @staticmethod
    # async def duplicate_until_entry_id_with_entries(
    #         chat_id: str,
    #         selective_entries_id: List[str],
    #         title: str,
    #         model: List[ModelWithParameters],
    # ) -> str:
    #     user_id = config.user_info_var.get().get("user_id")
    #
    #     # load the chat
    #     chat = await db_async.chats.find_one({"_id": ObjectId(chat_id)})
    #     if not chat:
    #         # Optional: raise if not found, to keep behavior explicit
    #         # from fastapi import HTTPException
    #         # from starlette import status
    #         # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    #         return ""
    #
    #     entries_id = [ObjectId(id_) for id_ in selective_entries_id]
    #     entries_cursor = (
    #         db_async.chat_entries
    #         .find(
    #             {
    #                 "chat_id": ObjectId(chat_id),
    #                 "_id": {"$in": entries_id},
    #             }
    #         )
    #         .sort("created_at", DESCENDING)
    #     )
    #
    #     # generate chat
    #     new_chat = {
    #         key: value
    #         for (key, value) in chat.items()
    #         if key not in ["_id", "user_id", "title", "estimate_total_cost"]
    #     }
    #     new_chat["user_id"] = ObjectId(user_id)
    #     new_chat["title"] = title or "Fork of " + (chat.get("title") or "(no title)")
    #     new_chat["created_at"] = datetime.datetime.now(datetime.timezone.utc)
    #     new_chat["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
    #     new_chat["branch_model"] = model[0].name
    #     new_chat["branch_from_chat_id"] = chat.get("_id")
    #
    #     insert_res = await db_async.chats.insert_one(new_chat)
    #     new_chat_id = insert_res.inserted_id
    #
    #     # copy entries
    #     async for e in entries_cursor:
    #         new_e = {key: value for (key, value) in e.items() if key not in ["_id", "chat_id"]}
    #         new_e["chat_id"] = new_chat_id
    #         await db_async.chat_entries.insert_one(new_e)
    #
    #     return str(new_chat_id)

    @staticmethod
    async def duplicate_until_assistant_entry_id(chat_id: str, entry_id: str):
        user_id = config.user_info_var.get().get("user_id")
        chat_oid = ObjectId(chat_id)
        entry_oid = ObjectId(entry_id)

        # load the chat
        chat = await db_async.chats.find_one({"_id": chat_oid})
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
            )

        target_entry = await db_async.chat_entries.find_one(
            {"_id": entry_oid, "chat_id": chat_oid}
        )
        if target_entry is None:
            raise HTTPException(status_code=404, detail="Target entry not found")

        # collect all entries to copy
        filter_query = {
            "chat_id": chat_oid,
            "created_at": {"$lt": target_entry["created_at"]},
            "$or": [
                {"role": {"$ne": "assistant"}},  # keep user/system msgs
                {
                    "role": "assistant",
                    "$or": [
                        {"is_alternative": {"$exists": False}},  # field absent
                        {"is_alternative": 0},  # main thread
                    ],
                },
            ],
        }
        id_cursor = db_async.chat_entries.find(filter_query, {"_id": 1}).sort(
            [("created_at", ASCENDING), ("is_alternative", ASCENDING)]
        )
        ids_to_copy = [doc["_id"] async for doc in id_cursor]
        if entry_oid not in ids_to_copy:
            ids_to_copy.append(entry_oid)

        # create new chat
        now = datetime.datetime.now(datetime.timezone.utc)
        title = (
            f'Branch - {chat.get("title", "(no title)")}'
            if not chat.get("title", "").startswith("Branch")
            else chat.get("title")
        )
        new_chat = {
            **{
                k: v
                for k, v in chat.items()
                if k not in {"_id", "user_id", "title", "estimate_total_cost"}
            },
            "user_id": ObjectId(user_id),
            "title": title,
            "created_at": now,
            "updated_at": now,
            "branch_from_chat_id": chat_oid,
        }
        new_chat_id = (await db_async.chats.insert_one(new_chat)).inserted_id

        # copy entries
        entry_cursor = db_async.chat_entries.find(
            {"_id": {"$in": ids_to_copy}}, {"_id": 0}
        ).sort("created_at", ASCENDING)
        async for entry in entry_cursor:
            entry["chat_id"] = new_chat_id
            # normalise assistant entries that will now be the main thread
            if entry["role"] == "assistant":
                entry["is_alternative"] = 0
            await db_async.chat_entries.insert_one(entry)

        return str(new_chat_id)
