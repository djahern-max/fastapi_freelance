from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import enum

from app import models, schemas
from app.oauth2 import get_current_user
from app.database import get_db

router = APIRouter()


class UserType(str, enum.Enum):
    client = "client"
    developer = "developer"


class RoleSelection(schemas.BaseModel):
    user_type: UserType


# In your routes file (e.g., auth.py)
@router.post("/auth/select-role", response_model=schemas.User)
async def set_user_role(
    role: schemas.UserRoleSelect,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Set the user's role (user_type) and mark that they no longer need role selection.
    """
    user = db.query(models.User).filter(models.User.id == current_user.id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user.user_type = role.user_type
    user.needs_role_selection = False

    db.commit()
    db.refresh(user)

    return user


@router.get("/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    """
    Get current user profile information.
    """
    return current_user
