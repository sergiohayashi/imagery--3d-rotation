# routes/login_routes.py
import os
from typing import List, Optional

from fastapi import APIRouter, Response
from passlib.context import CryptContext

from ..services.account_service import AccountService
from ..services.project_service import ProjectService
from ..services.user_service import UserService
from ..models.user import UserInDB, UserBase

import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from passlib.context import CryptContext
import jwt
from dotenv import load_dotenv

from dotenv import load_dotenv

load_dotenv("./.env.local-only")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "129600"))

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    # return True
    if not plain_password or not hash_password:
        return False
    print("verify_password plain_password", plain_password)
    print("verify_password hashed_password", hashed_password)
    print("verify_password hash_password()", hash_password(plain_password))
    verified = pwd_context.verify(plain_password, hashed_password)
    print("verify_password verified", verified)
    return verified


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update(
        {
            "exp": expire,
            "token_type": "custom_jwt",  # Custom claim to identify our token
        }
    )
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def is_custom_jwt_token(token: str) -> bool:
    """
    Determine if the token is a custom JWT token by checking for the 'token_type' claim.
    """
    try:
        # Decode the token without verifying the signature to inspect the payload
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        # Check if the token has the custom claim 'token_type': 'custom_jwt'
        return decoded_token.get("token_type") == "custom_jwt"
    except jwt.PyJWTError:
        return False


# Custom JWT token validation
def validate_custom_jwt_token(token: str):
    try:
        # Decode the JWT token using your secret key
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check if the token is expired
        if datetime.utcnow() > datetime.utcfromtimestamp(payload["exp"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
            )

        # Return the payload (which contains user info)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


def recover_from_custom_token(token: str):
    if is_custom_jwt_token(token):
        payload = validate_custom_jwt_token(token)
        print("payload", payload)
        return payload["email"], payload["fullname"], payload["tenant_id"]
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
