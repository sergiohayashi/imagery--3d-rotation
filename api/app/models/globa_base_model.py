from pydantic import BaseModel
from bson import ObjectId


class GlobalBaseModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: lambda oid: str(
                oid
            )  # Convert ObjectId to string for JSON encoding
        }
