from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app import models
from app.models import UserType

def search_users(db: Session, username_prefix: str, user_type: UserType = None, current_user_id: int = None, limit: int = 5):
    """
    Search for users whose usernames start with the given prefix.
    Optionally filter by user type and exclude current user.
    """
    query = db.query(models.User).filter(
        models.User.username.ilike(f"{username_prefix}%")
    )
    
    if user_type:
        query = query.filter(models.User.user_type == user_type)
    
    if current_user_id:
        query = query.filter(models.User.id != current_user_id)
    
    return query.limit(limit).all()

def search_developers(db: Session, username_prefix: str, limit: int = 5):
    """Search specifically for developers."""
    return search_users(db, username_prefix, user_type=UserType.developer, limit=limit)

def search_clients(db: Session, username_prefix: str, limit: int = 5):
    """Search specifically for clients."""
    return search_users(db, username_prefix, user_type=UserType.client, limit=limit)

def get_user_by_id(db: Session, user_id: int):
    """Get user by ID with profile information."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        if user.user_type == UserType.developer:
            user.developer_profile = db.query(models.DeveloperProfile).filter(
                models.DeveloperProfile.user_id == user.id
            ).first()
        elif user.user_type == UserType.client:
            user.client_profile = db.query(models.ClientProfile).filter(
                models.ClientProfile.user_id == user.id
            ).first()
    return user
