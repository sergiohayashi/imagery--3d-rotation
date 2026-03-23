from bson import ObjectId

from ..database import db


class AugmentedMessageService:
    @classmethod
    def get_augmented_message(cls, id) -> str:
        res = db.augmented_message_log.find_one({"_id": ObjectId(id)})
        if not res:
            return "not found"
        return {
            "content": res.get("content").get("retrieved_content"),
            "meta": res.get("meta"),
        }
