# routes/context_artifact_routes.py
from typing import List

from fastapi import APIRouter, Response
from starlette.responses import JSONResponse

from ..models.system_message import (
    SystemMessageBase,
    SystemMessageData,
    SystemMessageForUpdate,
)
from ..services import system_message_service

router = APIRouter()


@router.get("/system_messages", response_model=List[SystemMessageData])
def get_all_system_messages(project_id: str):
    return system_message_service.get_all_system_messages(project_id)


@router.get("/system_messages/shared", response_model=List[SystemMessageData])
def get_all_shared_system_messages(project_id: str, search_text: str):
    return system_message_service.get_all_shared_system_messages(
        project_id, search_text
    )


@router.post("/system_messages")
def create_system_message(system_message: SystemMessageBase):
    inserted = system_message_service.create_system_message(system_message)
    print("inserted", inserted)
    return JSONResponse(status_code=200, content=inserted)


@router.get("/system_messages/{id}")
def get_system_message_by_id(id: str):
    print("get_system_message_by_id called! id=", id)
    return system_message_service.get_system_message_by_id(id)


@router.put("/system_messages/{id}")
def update_system_message(id: str, system_message: SystemMessageForUpdate):
    system_message_service.update_system_message(id, system_message)
    return Response(status_code=200)


@router.delete("/system_messages/{id}")
def delete_system_message(id: str):
    system_message_service.delete_system_message(id)
    return Response(status_code=200)


@router.put("/system_messages/{id}/touch")
def update_system_message(id: str):
    system_message_service.touch(id)
    return Response(status_code=200)
