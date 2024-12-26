# middleware.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from . import database, oauth2, models
from sqlalchemy.exc import SQLAlchemyError
import logging
import pytz
from fastapi import status
from .database import get_db


logger = logging.getLogger(__name__)


async def require_active_subscription(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Middleware to check if a developer has an active subscription.
    Clients are allowed through without a subscription check.
    Raises HTTPException if a developer doesn't have an active subscription.
    """
    # If user is a client, no subscription needed
    if current_user.user_type == models.UserType.client:
        return current_user

    # For developers, check subscription status
    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == current_user.id)
        .order_by(models.Subscription.created_at.desc())
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required to engage with clients",
        )

    # Check if subscription is active and not expired
    current_time = datetime.now(pytz.UTC)

    # Ensure subscription_end is timezone-aware
    subscription_end = subscription.current_period_end
    if subscription_end.tzinfo is None:
        subscription_end = pytz.UTC.localize(subscription_end)

    if subscription.status != "active" or current_time > subscription_end:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your subscription has expired. Please renew to continue engaging with clients",
        )

    return current_user
