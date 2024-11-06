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

router = APIRouter(
    tags=["Authentication"]
)

# app/routers/login.py

@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(
        models.User.username == user_credentials.username
    ).first()

    if not user or not utils.verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials, please try again."
        )

    # Create token with "sub" claim for user ID
    access_token = oauth2.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/validate-token", response_model=schemas.UserOut)
async def validate_token(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Validate token and return user information"""
    try:
        # Log the incoming request details
        auth_header = request.headers.get('Authorization')
        logger.info(f"Validating token request received")
        logger.debug(f"Authorization header: {auth_header[:20]}..." if auth_header else "No auth header")
        
        # Log the current user details
        logger.info(f"User found: ID={current_user.id}, Username={current_user.username}")
        
        response_data = {
            "id": current_user.id,
            "username": current_user.username,
            "is_active": current_user.is_active
        }
        
        logger.info(f"Token validation successful for user {current_user.username}")
        logger.debug(f"Returning user data: {response_data}")
        
        return response_data
        
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        logger.exception("Detailed error information:")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user