from sqlalchemy.orm import joinedload, Session
from sqlalchemy import or_, and_
from typing import Optional, List
from fastapi import HTTPException
import re
from app import models, schemas
from app.crud.crud_project import get_or_create_general_requests_project
from app.models import Request

# ------------------ Utility Functions ------------------

def check_sensitive_content(content: str) -> bool:
    """Check if content contains sensitive information."""
    sensitive_patterns = [
        r'api[_-]key', r'password', r'secret', r'token', 
        r'access[_-]key', r'private[_-]key', r'auth', r'credential'
    ]
    content_lower = content.lower()
    return any(re.search(pattern, content_lower) for pattern in sensitive_patterns)

def has_edit_permission(db: Session, request: models.Request, user_id: int) -> bool:
    """Check if a user has permission to edit a request."""
    if request.user_id == user_id:
        return True
    share = db.query(models.RequestShare).filter(
        and_(
            models.RequestShare.request_id == request.id,
            models.RequestShare.shared_with_user_id == user_id,
            models.RequestShare.can_edit == True
        )
    ).first()
    return bool(share)

# ------------------ CRUD Operations ------------------

def create_request(db: Session, request: schemas.RequestCreate, user_id: int):
    """Create a new request, assigning it to 'General Requests' if no project ID is provided."""
    if request.project_id is None:
        general_project = get_or_create_general_requests_project(user_id=user_id, db=db)
        request.project_id = general_project.id
    
    contains_sensitive = check_sensitive_content(request.content)
    if request.is_public and contains_sensitive:
        raise HTTPException(status_code=400, detail="Cannot create public request with sensitive data")

    db_request = models.Request(
        **request.dict(),
        user_id=user_id,
        contains_sensitive_data=contains_sensitive
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request

def get_requests(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all requests with optional pagination."""
    return db.query(models.Request).offset(skip).limit(limit).all()

def get_requests_by_user(
    db: Session,
    user_id: int,
    project_id: Optional[int] = None,
    include_shared: bool = True,
    skip: int = 0,
    limit: int = 100
):
    """Get requests for a specific user with optional project filtering, including requests shared with the user."""
    query = db.query(models.Request).options(joinedload(models.Request.user))
    
    if project_id:
        query = query.filter(models.Request.project_id == project_id)
    
    own_requests = query.filter(models.Request.user_id == user_id)
    
    if include_shared:
        shared_requests_query = db.query(models.Request).join(
            models.RequestShare, 
            models.Request.id == models.RequestShare.request_id
        ).filter(models.RequestShare.shared_with_user_id == user_id)
        
        if project_id:
            shared_requests_query = shared_requests_query.filter(models.Request.project_id == project_id)
        
        query = own_requests.union(shared_requests_query)
    else:
        query = own_requests
    
    requests = query.offset(skip).limit(limit).all()
    
    result = []
    for request in requests:
        shares = db.query(models.RequestShare).join(
            models.User, 
            models.RequestShare.shared_with_user_id == models.User.id
        ).filter(
            models.RequestShare.request_id == request.id
        ).all()
        
        request_dict = {
            "id": request.id,
            "title": request.title,
            "content": request.content,
            "project_id": request.project_id,
            "user_id": request.user_id,
            "owner_username": request.user.username,
            "is_public": request.is_public,
            "created_at": request.created_at,
            "updated_at": request.updated_at,
            "contains_sensitive_data": request.contains_sensitive_data,
            "shared_with": [
                {
                    "user_id": share.shared_with_user_id,
                    "username": db.query(models.User)
                        .filter(models.User.id == share.shared_with_user_id)
                        .first().username,
                    "can_edit": share.can_edit
                }
                for share in shares
            ]
        }
        result.append(request_dict)
    
    return result

def get_public_requests(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all public requests without sensitive data."""
    return db.query(models.Request)\
        .filter(models.Request.is_public == True)\
        .filter(models.Request.contains_sensitive_data == False)\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_request_by_id(db: Session, request_id: int):
    """Retrieve a specific request by its ID."""
    return db.query(models.Request).filter(models.Request.id == request_id).first()

def update_request(
    db: Session, 
    request_id: int, 
    request_update: schemas.RequestUpdate, 
    user_id: int
):
    """Update an existing request, checking for edit permissions and sensitive content."""
    db_request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if not has_edit_permission(db, db_request, user_id):
        raise HTTPException(status_code=403, detail="Not authorized to edit this request")
    
    contains_sensitive = check_sensitive_content(request_update.content)
    if request_update.is_public and contains_sensitive:
        raise HTTPException(
            status_code=400,
            detail="Cannot make request public as it contains sensitive data"
        )
    
    for key, value in request_update.dict(exclude_unset=True).items():
        setattr(db_request, key, value)
    
    db_request.contains_sensitive_data = contains_sensitive
    db.commit()
    db.refresh(db_request)
    return db_request

def delete_request(db: Session, request_id: int, user_id: int):
    """Delete a request, ensuring only the owner can delete it."""
    db_request = db.query(models.Request).filter(models.Request.id == request_id).first()
    
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if db_request.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this request")
    
    db.query(models.RequestShare).filter(models.RequestShare.request_id == request_id).delete()
    
    db.delete(db_request)
    db.commit()
    
    return {"message": "Request deleted successfully"}

# ------------------ Sharing Functionality ------------------

def share_request(
    db: Session, 
    request_id: int, 
    user_id: int, 
    share: schemas.RequestShare
):
    """Share a request with another user, ensuring ownership and no sensitive data."""
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to share this request")
    
    if request.contains_sensitive_data:
        raise HTTPException(
            status_code=400,
            detail="Cannot share requests containing sensitive data"
        )
    
    existing_share = db.query(models.RequestShare).filter(
        and_(
            models.RequestShare.request_id == request_id,
            models.RequestShare.shared_with_user_id == share.shared_with_user_id
        )
    ).first()
    
    if existing_share:
        raise HTTPException(status_code=400, detail="Request is already shared with this user")
    
    db_share = models.RequestShare(
        request_id=request_id,
        shared_with_user_id=share.shared_with_user_id,
        can_edit=share.can_edit
    )
    db.add(db_share)
    db.commit()
    db.refresh(db_share)
    return db_share

def remove_share(
    db: Session, 
    request_id: int, 
    user_id: int, 
    shared_user_id: int
):
    """Remove sharing of a request for a specific user, ensuring ownership."""
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to modify sharing settings for this request"
        )
    
    share = db.query(models.RequestShare).filter(
        and_(
            models.RequestShare.request_id == request_id,
            models.RequestShare.shared_with_user_id == shared_user_id
        )
    ).first()
    
    if share:
        db.delete(share)
        db.commit()
    return share

def get_shared_requests(db: Session, user_id: int):
    """Get all requests that have been shared with the user."""
    shared_requests = (
        db.query(models.Request)
        .join(models.RequestShare, models.Request.id == models.RequestShare.request_id)
        .options(joinedload(models.Request.user))
        .filter(models.RequestShare.shared_with_user_id == user_id)
        .all()
    )
    
    result = []
    for request in shared_requests:
        owner_username = request.user.username if request.user else "Unknown"
        
        shares = db.query(models.RequestShare).join(
            models.User, models.RequestShare.shared_with_user_id == models.User.id
        ).filter(
            models.RequestShare.request_id == request.id
        ).all()
        
        request_dict = {
            "id": request.id,
            "title": request.title,
            "content": request.content,
            "project_id": request.project_id,
            "user_id": request.user_id,
            "owner_username": owner_username,
            "is_public": request.is_public,
            "created_at": request.created_at,
            "updated_at": request.updated_at,
            "contains_sensitive_data": request.contains_sensitive_data,
            "shared_with": [
                {
                    "user_id": share.shared_with_user_id,
                    "username": share.user.username,
                    "can_edit": share.can_edit
                }
                for share in shares
            ]
        }
        result.append(request_dict)
    
    return result

def toggle_request_privacy(db: Session, request_id: int, user_id: int, is_public: bool):
    """Toggle the privacy of a request if the user has permission."""
    request = db.query(Request).filter(Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this request")

    request.is_public = is_public
    db.commit()
    db.refresh(request)
    return request

def get_public_requests(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all public requests that serve as requests for help (e.g., public AI Agent or Automation requests)."""
    return (
        db.query(models.Request)
        .filter(models.Request.is_public == True)
        .filter(models.Request.contains_sensitive_data == False)
        .offset(skip)
        .limit(limit)
        .all()
    )
