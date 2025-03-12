# app/routers/login.py NEED TO WRITE THIS FOR A COMMIT MESSAGE
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app import database, models, utils, schemas, oauth2
from app.models import User
from app.oauth2 import get_current_user
from app.database import get_db
from typing import Optional

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
    try:
        print(f"DEBUG: /me endpoint called for user ID: {current_user.id}")
        print(f"DEBUG: Current user type: {current_user.user_type}")

        # Get profile information based on user type only if the type is set
        if current_user.user_type:
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

        # If user_type is None but needs_role_selection is False, set it to True
        if current_user.user_type is None and not getattr(
            current_user, "needs_role_selection", True
        ):
            # Update the user in the database
            current_user.needs_role_selection = True
            db.commit()

        # Add additional debugging for OAuth IDs
        print(
            f"DEBUG: OAuth IDs - Google: {current_user.google_id}, GitHub: {current_user.github_id}, LinkedIn: {current_user.linkedin_id}"
        )

        return current_user
    except Exception as e:
        print(f"DEBUG: Error in /me endpoint: {str(e)}")
        # Re-raise the exception to get the proper error response
        raise


@router.post("/select-role", status_code=status.HTTP_200_OK)
def select_user_role(
    user_role: schemas.UserRoleSelect,
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set or update the user role for a registered user.
    This is used especially after OAuth registration where the
    user needs to select their role after successful authentication.
    """
    try:
        # Get the current user from the database to ensure we're working with up-to-date data
        user = db.query(models.User).filter(models.User.id == current_user.id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Update user's type and role selection flag
        user.user_type = user_role.user_type
        user.needs_role_selection = False

        # Create appropriate profile based on user type
        if user_role.user_type == "developer" and not user.developer_profile:
            # Create an empty developer profile
            developer_profile = models.DeveloperProfile(
                user_id=user.id, skills="", experience_years=0, bio="", is_public=False
            )
            db.add(developer_profile)

        elif user_role.user_type == "client" and not user.client_profile:
            # Create an empty client profile
            client_profile = models.ClientProfile(user_id=user.id)
            db.add(client_profile)

        # Commit the changes
        db.commit()

        logger.info(f"User {user.id} selected role: {user_role.user_type}")

        return {
            "message": "User role updated successfully",
            "user_type": user.user_type,
            "needs_role_selection": user.needs_role_selection,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user role: {str(e)}",
        )


@router.get("/get-user", response_model=schemas.UserOut)
def get_user_by_oauth(
    google_id: Optional[str] = None,
    github_id: Optional[str] = None,
    linkedin_id: Optional[str] = None,
    db: Session = Depends(database.get_db),
):
    """Fetch user by OAuth provider ID"""
    user = None

    if google_id:
        user = db.query(models.User).filter(models.User.google_id == google_id).first()
    elif github_id:
        user = db.query(models.User).filter(models.User.github_id == github_id).first()
    elif linkedin_id:
        user = (
            db.query(models.User).filter(models.User.linkedin_id == linkedin_id).first()
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return user
