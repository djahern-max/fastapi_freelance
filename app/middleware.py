# middleware.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from . import database, oauth2, models


async def require_active_subscription(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    if current_user.user_type != models.UserType.developer:
        return current_user

    subscription = (
        db.query(models.Subscription)
        .filter(
            models.Subscription.user_id == current_user.id, models.Subscription.status == "active"
        )
        .first()
    )

    if not subscription:
        raise HTTPException(status_code=403, detail="Active subscription required")

    current_time = datetime.now(timezone.utc)
    if subscription.current_period_end.replace(tzinfo=timezone.utc) < current_time:
        raise HTTPException(status_code=403, detail="Subscription expired")

    return current_user
