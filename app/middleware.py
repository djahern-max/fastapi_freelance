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


async def require_active_subscription(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Middleware modified to allow all users through without subscription check.
    Kept for future reimplementation.

    TODO: When reactivating subscriptions:
    1. Re-implement subscription validation
    2. Add subscription status check
    3. Add period_end validation
    4. Restore client/developer differentiation
    """
    return current_user
