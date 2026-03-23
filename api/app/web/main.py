import logging
import traceback
from pathlib import Path

import exceptiongroup
from fastapi import FastAPI, Request, Response
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config.config import config
from app.config.global_config import LOCAL_FILES_MOUNT_PREFIX, the_global_config
from app.config.static_mounts import (
    DATASET_EVAL_IMAGES_DIR,
    PROBLEMS_IMAGES_DIR,
    MOUNT_DATASET_EVAL_IMAGES,
    MOUNT_PROBLEMS_IMAGES,
)
from ..config import custom_auth

# from ..config.auth import validate_and_extract_token
from ..routes import login_routes, file_routes, file_context_routes
from ..routes import (
    user_project_routes,
    project_routes,
    chat_entry_routes,
    chat_routes,
    chat_message_routes,
    system_message_routes,
    account_routes,
    upload_routes,
    shared_chat_routes,
    models_routes,
    llm_task_routes,
    bookmark_routes,
)
from ..services.user_service import UserService

logger = logging.getLogger(__name__)

app = FastAPI(
    docs_url=None,  # Disable /docs (avoids PydanticInvalidForJsonSchema for ObjectId)
    redoc_url=None,
    openapi_url=None,
)


# Set up CORS
origins = ["*"]


# Include the routes from project_routes
app.include_router(login_routes.router, prefix="")
app.include_router(project_routes.router, prefix="/api")
app.include_router(user_project_routes.router, prefix="/api")
app.include_router(chat_routes.router, prefix="/api")
app.include_router(chat_entry_routes.router, prefix="/api")
app.include_router(chat_message_routes.router, prefix="/api")
app.include_router(system_message_routes.router, prefix="/api")
app.include_router(account_routes.router, prefix="/api")
app.include_router(upload_routes.router, prefix="/api")
app.include_router(shared_chat_routes.router, prefix="/api")
app.include_router(models_routes.router, prefix="/api")
app.include_router(llm_task_routes.router, prefix="/api")
app.include_router(bookmark_routes.router, prefix="/api")
app.include_router(file_routes.router, prefix="/api")
app.include_router(file_context_routes.router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# @app.exception_handler(Exception)
# MEMO: Don't works well, so the error is handled in the AuthMiddleware
async def exception_handler(request: Request, e: Exception):
    def extract_root_cause(e):
        if isinstance(e, exceptiongroup.ExceptionGroup):
            # Get the last exception in the group
            last_exception = e.exceptions[-1]
            return extract_root_cause(last_exception)
        else:
            # Return the message of the non-ExceptionGroup exception
            return str(e)

    def extract_exception_details():
        if isinstance(e, HTTPException):
            return e.detail, e.status_code
        elif isinstance(e, StarletteHTTPException):
            return e.detail, e.status_code
        elif isinstance(e, exceptiongroup.ExceptionGroup):
            details = [extract_root_cause(ex) for ex in e.exceptions]
            return " ".join(details), getattr(e, "status_code", None)
        else:
            return str(e), None

    detail, status_code = extract_exception_details()
    print(
        f"[exception_handler] type(e)= {type(e)}, detail: [{detail}] status_code={status_code}"
    )
    headers = {}
    if request.headers.get("origin"):
        headers["Access-Control-Allow-Origin"] = request.headers["origin"]
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Methods"] = "*"
        headers["Access-Control-Allow-Headers"] = "*"
    return JSONResponse(
        status_code=(
            status_code if status_code else status.HTTP_500_INTERNAL_SERVER_ERROR
        ),
        content=detail,
        headers=headers,
    )


# mount static files folder — dirs from app.config.static_mounts
from fastapi.staticfiles import StaticFiles


def _mount_static_if_dir_exists(mount_path: str, directory: Path, *, name: str) -> None:
    """Register StaticFiles only if ``directory`` exists; avoids startup failure."""
    resolved = Path(directory).resolve()
    if not resolved.is_dir():
        logger.warning(
            "Skipping static mount %r: not an existing directory: %s",
            name,
            resolved,
        )
        return
    app.mount(
        mount_path,
        StaticFiles(directory=str(resolved)),
        name=name,
    )
    logger.info(f"MOUNTED static files: {name} -> {resolved}")


_mount_static_if_dir_exists(
    MOUNT_DATASET_EVAL_IMAGES,
    DATASET_EVAL_IMAGES_DIR,
    name="images",
)
_mount_static_if_dir_exists(
    MOUNT_PROBLEMS_IMAGES,
    PROBLEMS_IMAGES_DIR,
    name="spatialviz_images",
)
_mount_static_if_dir_exists(
    LOCAL_FILES_MOUNT_PREFIX,
    Path(the_global_config.local_files_root_dir),
    name="local_bucket_files",
)


@app.get("/")
def read_root():
    return {"message": "Welcome to Imagery!"}



@app.post("/register")
async def register(user_args: dict):
    if not user_args.get("tenant_id") or user_args["tenant_id"] not in config.tenants:
        print(f"Tenant {user_args.get('tenant_id')} invalid!")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your organization or tenant is not allowed to access this application. Please contact your administrator.",
        )
    return UserService.register(
        user_args["email"], user_args["name"], user_args["tenant_id"]
    )


class TokenData(BaseModel):
    token: str


@app.post("/register-from-token-for-email")
def register_from_token_for_email(token: TokenData):
    email, name, tenant_id = custom_auth.recover_from_custom_token(token.token)
    print("register_from_token_for_email.", email, name, tenant_id)
    return UserService.register(email, name, tenant_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
