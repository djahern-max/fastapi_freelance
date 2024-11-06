# app/oauth2.py
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from . import schemas, database, models
from .config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

def create_access_token(data: dict):
    """Create JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    logger.debug(f"Creating token with payload: {to_encode}")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str, credentials_exception=None):
    """Verify JWT token and return token data"""
    try:
        logger.debug(f"Attempting to decode token: {token[:20]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"Token payload decoded: {payload}")
        
        # Check for user_id in payload
        id: str = payload.get("sub")  # or "user_id" depending on your create_access_token
        if id is None:
            logger.error("No user ID found in token payload")
            raise credentials_exception or HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials: No user ID in token",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        token_data = schemas.TokenData(id=id)  # Make sure this matches your schema
        logger.info(f"Token successfully verified for user ID: {id}")
        return token_data
        
    except JWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise credentials_exception or HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db)
):
    """Get current user from token"""
    logger.info("Attempting to get current user from token")
    
    try:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        token_data = verify_access_token(token, credentials_exception)
        logger.debug(f"Token data retrieved: {token_data}")
        
        # Use id instead of user_id to match the schema
        user = db.query(models.User).filter(models.User.id == token_data.id).first()
        if not user:
            logger.error(f"No user found for ID: {token_data.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        logger.info(f"Successfully retrieved user: {user.username}")
        return user
        
    except Exception as e:
        logger.error(f"Error in get_current_user: {str(e)}")
        logger.exception("Detailed error information:")
        raise
 