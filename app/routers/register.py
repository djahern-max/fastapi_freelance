# app/routers/register.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import database, models, schemas, utils
from app.models import User
from typing import Optional

router = APIRouter(tags=["Users"])


@router.post("/register", response_model=schemas.UserOut)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # First check terms
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
            terms_accepted=user.terms_accepted,
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
        # Don't silently catch exceptions! Either log them or re-raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}",
        )
