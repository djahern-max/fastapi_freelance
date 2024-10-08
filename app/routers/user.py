import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import models, schemas, utils, database

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Users"]
)

@router.post("/", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # Log the registration attempt
    logger.info(f"Registration attempt for email: {user.email}")

    # Check if the user with the given email already exists
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    
    if existing_user:
        logger.warning(f"Registration failed: Email {user.email} is already registered")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash the password before storing it
    hashed_password = utils.hash_password(user.password)
    logger.info(f"Password hashed successfully for email: {user.email}")

    # Create the new user
    db_user = models.User(email=user.email, password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    logger.info(f"User created successfully with ID: {db_user.id} for email: {user.email}")

    return db_user




