import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import database, models, utils, schemas, oauth2
from app.models import User
from app.oauth2 import get_current_user

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Authentication"]
)

# Updated login route using JSON (application/json)
@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == user_credentials.username).first()

    if not user or not utils.verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials, please try again."
        )

    # Use the create_access_token from oauth2.py
    access_token = oauth2.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/validate-token", response_model=schemas.User)
async def validate_token(current_user: models.User = Depends(oauth2.get_current_user)):
    return {"username": current_user.username}

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/users/{id}")
def get_user(id: int, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
