from fastapi import APIRouter

from ..config.config import config
from ..services.user_service import UserService

from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel

from ..config import custom_auth

router = APIRouter()


class LoginForm(BaseModel):
    email: str
    password: str


class TokenData(BaseModel):
    email: str
    fullname: str


@router.post("/login")
def login_by_email_password(form_data: LoginForm):

    email = form_data.email.lower()
    user = UserService.verify_user_and_password(email, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    UserService.register(email, user["name"], user["tenant_id"])

    # Create JWT token
    access_token_expires = timedelta(minutes=custom_auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "email": email,
        "fullname": user["name"],
        "tenant_id": user["tenant_id"],
    }
    access_token = custom_auth.create_access_token(
        data=token_data, expires_delta=access_token_expires
    )

    response = {
        "access_token": access_token,
        "token_type": "bearer",
        "profile": {
            "name": user["name"],
            "email": email,
            "tenant_id": user["tenant_id"],
            "permissions": ["manager"] if user["email"] in config.managers else [],
        },
    }

    print("/login. response = ", response)
    return response
