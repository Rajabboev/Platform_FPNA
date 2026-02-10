"""Approval schemas"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ApproveRejectRequest(BaseModel):
    comment: Optional[str] = None


class ApprovalRecordResponse(BaseModel):
    id: int
    user_username: Optional[str]
    level: int
    action: str
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
