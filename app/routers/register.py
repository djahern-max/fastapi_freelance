# app/routers/register.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import database, models, schemas, utils
from app.models import User
from typing import Optional

router = APIRouter(tags=["Users"])


@router.post("/register", response_model=schemas.UserOut)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """Register a new user with basic information. Profiles can be added later."""
    if not user.terms_accepted:
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
