# app/routers/register.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import database, models, schemas
from app import utils
from app.models import User
from typing import Optional

router = APIRouter(tags=["Users"])


@router.post("/register", response_model=schemas.UserOut)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    try:
        # First check terms
        if not user.terms_accepted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must accept the terms of agreement to register.",
            )

        # Log what we're about to do
        print(f"Registering user: {user.email}, username: {user.username}")

        # Check if username already exists
        existing_user = (
            db.query(models.User).filter(models.User.username == user.username).first()
        )
        if existing_user:
            print(f"Username already taken: {user.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
            )

        # Check if email already exists
        existing_email = (
            db.query(models.User).filter(models.User.email == user.email).first()
        )
        if existing_email:
            print(f"Email already registered: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create new user with hashed password - use the imported hash_password function
        print("Hashing password...")
        hashed_password = utils.hash_password(user.password)

        print("Creating user object...")
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
        print("Adding to database...")
        db.add(new_user)

        print("Committing to database...")
        db.commit()

        print("Refreshing user object...")
        db.refresh(new_user)

        print(f"User created: {new_user.id}, {new_user.username}")
        return new_user

    except Exception as e:
        print(f"Error during registration: {type(e).__name__}: {str(e)}")
        db.rollback()
        # Re-raise but with more detail
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {type(e).__name__}: {str(e)}",
        )
