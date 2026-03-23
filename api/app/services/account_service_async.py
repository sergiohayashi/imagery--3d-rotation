# # services/user_service.py
# from typing import Optional
#
# from bson import ObjectId
# from fastapi import HTTPException, status
#
# from ..database import db
# from .usage_log_service import UsageLogService, usage_log_service
# from app.services.usage_log_service_async import UsageLogServiceAsync
# from ..config.config import config
#
#
# class AccountServiceAsync:
#     @staticmethod
#     def get_current_balance():
#         user_id = config.user_info_var.get().get('user_id')
#         if not user_id:
#             raise HTTPException(detail="Invalid user or without permission", status_code=status.HTTP_400_BAD_REQUEST)
#         return usage_log_service.get_current_usage(user_id)
#
#     @staticmethod
#     def get_ranking(top: Optional[int] = 3, month: Optional[int] = 0, year: Optional[int] = 0):
#         return usage_log_service.get_ranking(top, month, year)
#
