# routes/user_routes.py
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.account_service import AccountService
from ..services.user_service import UserService

router = APIRouter()


@router.get("/account/balance")
def get_current_balance():
    return AccountService.get_current_balance()


# Pydantic models
class SetPasswordForm(BaseModel):
    password: str


@router.post("/account/set-password")
def set_password(args: SetPasswordForm):
    return UserService.update_password(args.password)


@router.put("/account/exclude-from-ranking/switch")
def switch_exclude_from_ranking():
    return AccountService.switch_exclude_from_ranking()


@router.get("/account/exclude-from-ranking")
def get_exclude_from_ranking():
    return AccountService.get_exclude_from_ranking()
