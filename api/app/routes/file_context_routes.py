from typing import List

from fastapi import APIRouter, Response
from starlette.responses import JSONResponse

from ..models.file_context import FileContext, RagContextFile
from ..services import system_message_service, file_context_service

router = APIRouter()


@router.get("/file_context")
async def get_all(project_id: str):
    return await file_context_service.get_all(project_id)


@router.post("/file_context")
async def create_new(args: FileContext):
    inserted = await file_context_service.create_new(args)
    print("inserted", inserted)
    return JSONResponse(status_code=200, content=inserted)


@router.put("/file_context/{_id}")
async def update(_id: str, args: FileContext):
    await file_context_service.update(_id, args)
    return Response(status_code=200)


@router.get("/file_context/{id}")
async def get(id: str):
    return await file_context_service.get_one(id)


@router.delete("/file_context/{id}")
async def delete(id: str):
    await file_context_service.delete_file_context(id)
    return Response(status_code=200)


@router.get("/file_context/{id}/files")
async def get_files(id: str):
    return await file_context_service.get_files(id)


@router.delete("/file_context/{id}/files/{file_id}")
async def delete_file(id: str, file_id: str):
    inserted = await file_context_service.delete_file(id, file_id)
    print("inserted", inserted)
    return JSONResponse(status_code=200, content=inserted)
