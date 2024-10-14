from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt  # Consistently using jose
from datetime import datetime, timedelta
from typing import Optional
from . import schemas
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app import database, models
from sqlalchemy.orm import Session
from .config import settings
import logging

logger = logging.getLogger(__name__)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SECRET_KEY = settings.secret_key  
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return schemas.TokenData(id=user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except JWTError:
        raise credentials_exception

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    token_data = verify_access_token(token, credentials_exception)
    logger.info(f"Token Data ID: {token_data.id}")  # Log token data

    user = db.query(models.User).filter(models.User.id == token_data.id).first()
    if user is None:
        logger.error(f"User not found for ID: {token_data.id}")  # Log error if user not found
        raise credentials_exception

    logger.info(f"Current User: {user.username}, ID: {user.id}")  # Log the user details
    return user


    


              
 