# app/api/chat_export.py
from datetime import datetime
from pathlib import Path
import tempfile
import zipfile
import shutil
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from bson import ObjectId

from app.database_async import db_async

# from app.dependencies import get_db  # returns Motor client or similar
# from app.models.user import User     # whatever you use for auth

# router = APIRouter()
MAX_EXPORT_ENTRIES = 20_000


def sanitize(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value or "")


def chat_filename(chat) -> str:
    created_at = chat["created_at"].strftime("%Y%m%d%H%M%S")
    title = sanitize(chat.get("title") or "chat")
    return f"{created_at}_{title}.txt"


def zip_filename(project_name: str, start: datetime, end: datetime) -> str:
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    project = sanitize(project_name)
    return f"Imagery_{project}_{start:%Y%m%d}-{end:%Y%m%d}_{now}.zip"


def cleanup_temp_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


async def write_chat_file(text_dir: Path, chat, db, start, end):
    entries_cursor = db.chat_entries.find(
        {
            "chat_id": chat["_id"],
            "created_at": {"$gte": start, "$lt": end},
        }
    ).sort("created_at", 1)

    lines = []
    async for entry in entries_cursor:
        image = f"\n[{entry['image_url']}]" if "image_url" in entry else ""
        lines.append(f"{entry['role']}:\n{entry['content']}{image}")

    if not lines:
        return False

    file_path = text_dir / chat_filename(chat)
    file_path.write_text("\n\n".join(lines), encoding="utf-8")
    return True


async def build_zip_archive(temp_dir: Path, zip_name: str) -> Path:
    zip_path = temp_dir / zip_name
    text_dir = temp_dir / "files"

    def _zip():
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for txt in text_dir.iterdir():
                zf.write(txt, arcname=txt.name)

    await asyncio.to_thread(_zip)
    return zip_path


async def export_chat(project_id: str, year: int, background_tasks):
    project = await db_async.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    temp_dir = Path(tempfile.mkdtemp(prefix="chat-export-"))
    text_dir = temp_dir / "files"
    text_dir.mkdir(exist_ok=True)

    # Calculate the start and end of the given year
    start = datetime(year, 1, 1, 0, 0, 0)
    end = datetime(year + 1, 1, 1, 0, 0, 0)

    chat_filter = {
        "project_id": project["_id"],
        "created_at": {"$gte": start, "$lt": end},
    }
    chat_cursor = (
        db_async.chats.find(chat_filter).sort("created_at", 1).limit(MAX_EXPORT_ENTRIES)
    )

    try:
        exported_any = False
        async for chat in chat_cursor:
            exported = await write_chat_file(text_dir, chat, db_async, start, end)
            exported_any = exported_any or exported

        if not exported_any:
            cleanup_temp_dir(temp_dir)
            raise HTTPException(
                status_code=404, detail="No chats in the chosen period."
            )

        archive_name = zip_filename(project["name"], start, end)
        zip_path = await build_zip_archive(temp_dir, archive_name)

        background_tasks.add_task(cleanup_temp_dir, temp_dir)
        return FileResponse(
            path=zip_path,
            filename=archive_name,
            media_type="application/zip",
            background=background_tasks,
        )
    except ValueError as exc:
        cleanup_temp_dir(temp_dir)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        cleanup_temp_dir(temp_dir)
        raise


async def count_chat(project_id: str, year):
    project = await db_async.projects.find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    # Calculate the start and end of the given year
    start = datetime(year, 1, 1, 0, 0, 0)
    end = datetime(year + 1, 1, 1, 0, 0, 0)

    chat_filter = {
        "project_id": project["_id"],
        "created_at": {"$gte": start, "$lt": end},
    }
    return await db_async.chats.count_documents(chat_filter)
