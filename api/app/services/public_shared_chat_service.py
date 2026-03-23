from fastapi import HTTPException
from starlette import status
from ..database import db
from datetime import datetime, timezone


class PublicSharedChatService:

    @staticmethod
    def get_chat_thread(shared_id) -> dict:
        chat = db.chats.find_one({"shared_id": shared_id})
        if not chat:
            raise HTTPException(
                detail="Invalid ID", status_code=status.HTTP_400_BAD_REQUEST
            )
        print("chat: ", chat)
        if chat["shared_id_expire_date"].date() < datetime.now(timezone.utc).date():
            raise HTTPException(
                detail="Shared ID has expired", status_code=status.HTTP_400_BAD_REQUEST
            )

        chat_id = chat["_id"]
        entries = db.chat_entries.find({"chat_id": chat_id}, sort=[("created_at", 1)])
        entries_list = []
        for entry in entries:
            new_entry = dict(
                role=entry.get("role"),
                content=entry.get("content"),
                image_url=entry.get("image_url"),
                file_url=entry.get("file_url"),
                file_name=entry.get("file_name"),
                content_type=entry.get("content_type"),
                created_at=entry.get("created_at"),
                is_alternative=entry.get("is_alternative", 0),
                augmented_message_log_id=(
                    str(entry.get("augmented_message_log_id"))
                    if entry.get("augmented_message_log_id")
                    else None
                ),
                meta=(
                    {
                        "model": entry["meta"].get("model"),
                        "company": entry["meta"].get("company"),
                    }
                    if entry.get("meta")
                    else None
                ),
                output=entry.get("output"),
            )
            if (
                new_entry.get("is_alternative", 0) > 0
                and len(entries_list) > 0
                and len(entries_list[-1]) > 0
                and entries_list[-1][0].get("created_at") == new_entry.get("created_at")
            ):
                entries_list[-1].append(new_entry)
            else:
                entries_list.append([new_entry])

        result = dict(
            title=chat["title"],
            created_at=chat["created_at"],
            shared_id_expire_date=chat["shared_id_expire_date"],
            entries=entries_list,
        )
        return result
