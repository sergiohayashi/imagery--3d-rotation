# routes/user_project_routes.py
from typing import List

from fastapi import APIRouter, Response

from ..services.bookmark_service import BookmarkService
from ..services.project_service import ProjectService

router = APIRouter()


@router.post("/bookmarks/{chat_id}")
def set_bookmark(chat_id: str):
    BookmarkService.set_bookmark(chat_id)


@router.delete("/bookmarks/{chat_id}")
def remove_bookmark(chat_id):
    BookmarkService.remove_bookmark(chat_id)


@router.put("/bookmarks/{chat_id}/toggle")
def remove_bookmark(chat_id):
    return BookmarkService.toggle(chat_id)
