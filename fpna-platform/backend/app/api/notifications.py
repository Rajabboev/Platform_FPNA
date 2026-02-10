"""
Notifications API - list, mark as read, unread count
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.utils.dependencies import get_current_active_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    unread_only: bool = Query(False, description="Filter to unread only"),
    limit: int = Query(50, ge=1, le=100),
):
    """List notifications for current user."""
    q = db.query(Notification).filter(Notification.recipient_id == current_user.id)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    items = q.all()
    return {
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "budget_id": n.budget_id,
                "budget_code": n.budget_code,
                "actor_username": n.actor_username,
                "message": n.message,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ],
    }


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get count of unread notifications."""
    count = db.query(Notification).filter(
        Notification.recipient_id == current_user.id,
        Notification.read_at.is_(None),
    ).count()
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as read."""
    from datetime import datetime, timezone
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.recipient_id == current_user.id,
    ).first()
    if not n:
        return {"ok": False, "detail": "Not found"}
    n.read_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read."""
    from datetime import datetime, timezone
    db.query(Notification).filter(
        Notification.recipient_id == current_user.id,
        Notification.read_at.is_(None),
    ).update({"read_at": datetime.now(timezone.utc)})
    db.commit()
    return {"ok": True}
