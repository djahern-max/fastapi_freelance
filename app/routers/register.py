# app/routers/register.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import database, models, schemas, utils
from app.models import User
from typing import Optional
from fastapi import Request


router = APIRouter(tags=["Users"])


@router.post("/register", response_model=schemas.UserOut)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """Register a new user with basic information. Profiles can be added later."""
    # Add this debug line
    print(f"Registration attempt: {user.dict()}")

    if not user.terms_accepted:
        # Add this debug line
        print("Terms not accepted")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the terms of agreement to register.",
        )

    # Check if username already exists
    existing_user = (
        db.query(models.User).filter(models.User.username == user.username).first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Check if email already exists
    existing_email = (
        db.query(models.User).filter(models.User.email == user.email).first()
    )

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user with hashed password
    try:
        hashed_password = utils.hash_password(user.password)
        new_user = models.User(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            password=hashed_password,
            user_type=user.user_type.lower(),
            is_active=True,
            terms_accepted=user.terms_accepted,  # Include this field
        )

        # Save user to database
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        print(
            "DEBUG:",
            type(new_user),
            new_user.__dict__ if hasattr(new_user, "__dict__") else new_user,
        )

        return new_user

    except Exception as e:
        db.rollback()


@router.get("/users/{id}", response_model=schemas.UserOut)
def get_user(id: int, db: Session = Depends(database.get_db)):
    """Get user by ID"""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id: {id} does not exist",
        )

    # Get profile information based on user type
    if user.user_type == models.UserType.developer:
        user.developer_profile = (
            db.query(models.DeveloperProfile)
            .filter(models.DeveloperProfile.user_id == user.id)
            .first()
        )
    elif user.user_type == models.UserType.client:
        user.client_profile = (
            db.query(models.ClientProfile)
            .filter(models.ClientProfile.user_id == user.id)
            .first()
        )

    return user


@router.post("/debug-register")
async def debug_register(request: Request, db: Session = Depends(database.get_db)):
    """Debug endpoint for registration issues"""
    try:
        body = await request.json()
        print(f"DEBUG REGISTER: {body}")

        # Check if username exists
        username_exists = (
            db.query(models.User)
            .filter(models.User.username == body.get("username"))
            .first()
            is not None
        )

        # Check if email exists
        email_exists = (
            db.query(models.User).filter(models.User.email == body.get("email")).first()
            is not None
        )

        # Check terms acceptance
        terms_accepted = body.get("terms_accepted", False)

        # Return diagnostic info
        return {
            "received_data": {
                k: "***" if k == "password" else v for k, v in body.items()
            },
            "validation_checks": {
                "terms_accepted": terms_accepted,
                "username_exists": username_exists,
                "email_exists": email_exists,
            },
            "required_fields": [
                "username",
                "email",
                "password",
                "terms_accepted",
                "user_type",
            ],
        }
    except Exception as e:
        return {"error": str(e)}
