from pydantic import BaseModel, validator, ValidationError
from enum import Enum


class Role(str, Enum):
    admin = "admin"
    contributor = "contributor"
