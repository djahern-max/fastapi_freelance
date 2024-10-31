from sqlalchemy.orm import Session
from sqlalchemy import and_
from app import models

def search_users(db: Session, username_prefix: str, limit: int = 5):
    """
    Search for users whose usernames start with the given prefix.
    
    Args:
        db: Database session
        username_prefix: String to search for at the start of usernames
        limit: Maximum number of results to return
    
    Returns:
        List of User objects matching the search criteria
    """
    return db.query(models.User).filter(
        models.User.username.ilike(f"{username_prefix}%")
    ).limit(limit).all()