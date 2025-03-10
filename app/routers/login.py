# app/routers/login.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app import database, models, utils, schemas, oauth2
from app.models import User
from app.oauth2 import get_current_user

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    user = (
        db.query(models.User)
        .filter(models.User.username == user_credentials.username)
        .first()
    )

    if not user or not utils.verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials, please try again.",
        )

    # Create token with string ID
    access_token = oauth2.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/validate-token", response_model=schemas.UserOut)
async def validate_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    # Log the incoming request details
    auth_header = request.headers.get("Authorization")

    # Log the current user details

    # Get profile information based on user type
    profile = None
    if current_user.user_type == models.UserType.developer:
        profile = (
            db.query(models.DeveloperProfile)
            .filter(models.DeveloperProfile.user_id == current_user.id)
            .first()
        )
    elif current_user.user_type == models.UserType.client:
        profile = (
            db.query(models.ClientProfile)
            .filter(models.ClientProfile.user_id == current_user.id)
            .first()
        )

    response_data = {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "user_type": current_user.user_type,
        "created_at": current_user.created_at,
    }

    return response_data


@router.get("/me", response_model=schemas.UserOut)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get current user information"""
    # Get profile information based on user type
    if current_user.user_type == models.UserType.developer:
        current_user.developer_profile = (
            db.query(models.DeveloperProfile)
            .filter(models.DeveloperProfile.user_id == current_user.id)
            .first()
        )
    elif current_user.user_type == models.UserType.client:
        current_user.client_profile = (
            db.query(models.ClientProfile)
            .filter(models.ClientProfile.user_id == current_user.id)
            .first()
        )

    return current_user


@router.post("/select-role")
def select_role(
    role_data: schemas.UserRoleSelect,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Set the role for a user after OAuth registration"""

    try:
        # Add extensive logging
        print(
            f"DEBUG: Setting role for user {current_user.id} to {role_data.user_type}"
        )
        print(f"DEBUG: Current user data: {current_user}")

        # Update user type
        current_user.user_type = role_data.user_type
        current_user.needs_role_selection = False  # Mark as completed role selection

        # Create appropriate profile based on role
        if role_data.user_type == models.UserType.developer:
            # Check if profile already exists
            existing_profile = (
                db.query(models.DeveloperProfile)
                .filter(models.DeveloperProfile.user_id == current_user.id)
                .first()
            )

            if not existing_profile:
                developer_profile = models.DeveloperProfile(
                    user_id=current_user.id,
                )
                db.add(developer_profile)
        else:  # client
            # Check if profile already exists
            existing_profile = (
                db.query(models.ClientProfile)
                .filter(models.ClientProfile.user_id == current_user.id)
                .first()
            )

            if not existing_profile:
                client_profile = models.ClientProfile(
                    user_id=current_user.id,
                )
                db.add(client_profile)

        # Commit the changes
        db.commit()
        db.refresh(current_user)

        print(f"DEBUG: Updated user data: {current_user}")
        print(f"DEBUG: User role set successfully to {current_user.user_type}")

        # Return success response with user type
        return {
            "message": "User role set successfully",
            "user_type": current_user.user_type,
        }

    except Exception as e:
        db.rollback()
        print(f"DEBUG: Error setting user role: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to set user role: {str(e)}"
        )
