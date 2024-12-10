# middleware.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from . import database, oauth2, models
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)


async def require_active_subscription(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    if current_user.user_type != models.UserType.developer:
        return current_user

    try:
        subscription = (
            db.query(models.Subscription)
            .filter(
                models.Subscription.user_id == current_user.id,
                models.Subscription.status == "active",
            )
            .first()
        )

        if not subscription:
            raise HTTPException(status_code=403, detail="Active subscription required")

        # Ensure both times are in UTC for comparison
        current_time = datetime.now(timezone.utc)
        subscription_end = subscription.current_period_end

        # Add UTC timezone if not present
        if subscription_end.tzinfo is None:
            subscription_end = subscription_end.replace(tzinfo=timezone.utc)

        if subscription_end < current_time:
            # Update subscription status to expired
            subscription.status = "expired"
            db.commit()
            raise HTTPException(status_code=403, detail="Subscription expired")

        return current_user
    except SQLAlchemyError as e:
        logger.error(f"Database error checking subscription: {str(e)}")
        raise HTTPException(status_code=500, detail="Error checking subscription status")
