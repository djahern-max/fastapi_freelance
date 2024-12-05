# middleware.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.oauth2 import get_current_user
from app import models
from datetime import datetime, timezone


async def require_active_subscription(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    # Skip check for non-developers
    if current_user.user_type != models.UserType.developer:
        return current_user

    subscription = (
        db.query(models.Subscription).filter(models.Subscription.user_id == current_user.id).first()
    )

    if not subscription or subscription.status != "active":
        raise HTTPException(status_code=403, detail="Active subscription required")

    if subscription.current_period_end < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Subscription has expired")

    return current_user
