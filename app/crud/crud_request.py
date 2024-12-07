from sqlalchemy.orm import joinedload, Session
from sqlalchemy import and_, or_
from typing import Optional
from fastapi import HTTPException, status
import re
from app import models, schemas
from sqlalchemy.orm import joinedload, contains_eager
from typing import Optional
from app import models, schemas
from sqlalchemy.orm import joinedload, contains_eager
from sqlalchemy import and_
from fastapi import HTTPException, status
from datetime import datetime

# ------------------ Utility Functions ------------------


def check_sensitive_content(content: str) -> bool:
    """Check if content contains sensitive information."""
    sensitive_patterns = [
        r"api[_-]key",
        r"password",
        r"secret",
        r"token",
        r"access[_-]key",
        r"private[_-]key",
        r"auth",
        r"credential",
    ]
    return any(re.search(pattern, content.lower()) for pattern in sensitive_patterns)


def has_edit_permission(db: Session, request: models.Request, user_id: int) -> bool:
    """Check if a user has permission to edit a request."""
    return (
        request.user_id == user_id
        or db.query(models.RequestShare)
        .filter(
            and_(
                models.RequestShare.request_id == request.id,
                models.RequestShare.shared_with_user_id == user_id,
                models.RequestShare.can_edit == True,
            )
        )
        .first()
    )


# ------------------ CRUD Operations ------------------


def create_request(db: Session, request: schemas.RequestCreate, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()

    db_request = models.Request(
        title=request.title,
        content=request.content,
        project_id=request.project_id,
        user_id=user_id,
        is_public=request.is_public,
        contains_sensitive_data=request.contains_sensitive_data,
        estimated_budget=request.estimated_budget,
    )

    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # Add the owner_username to the response
    setattr(db_request, "owner_username", user.username)
    return db_request


def get_requests_by_user(
    db: Session,
    user_id: int,
    project_id: Optional[int] = None,
    include_shared: bool = True,
    skip: int = 0,
    limit: int = 100,
):
    """Get requests for a specific user with optional project filtering, including shared requests."""
    query = (
        db.query(models.Request)
        .join(models.User, models.Request.user_id == models.User.id)
        .options(contains_eager(models.Request.user))
        .options(joinedload(models.Request.shared_with).joinedload(models.RequestShare.user))
        .filter(models.Request.user_id == user_id)
    )

    if project_id:
        query = query.filter(models.Request.project_id == project_id)

    if include_shared:
        shared_requests_query = (
            db.query(models.Request)
            .join(models.User, models.Request.user_id == models.User.id)
            .options(contains_eager(models.Request.user))
            .options(joinedload(models.Request.shared_with).joinedload(models.RequestShare.user))
            .join(models.RequestShare, models.Request.id == models.RequestShare.request_id)
            .filter(models.RequestShare.shared_with_user_id == user_id)
        )

        if project_id:
            shared_requests_query = shared_requests_query.filter(
                models.Request.project_id == project_id
            )

        query = query.union(shared_requests_query)

    requests = query.offset(skip).limit(limit).all()

    # Transform the requests
    for request in requests:
        request.owner_username = request.user.username
        # Create a new attribute for transformed shared_with data
        request.shared_with_info = []
        for share in request.shared_with:
            if hasattr(share, "user"):
                request.shared_with_info.append(
                    {
                        "user_id": share.user.id,
                        "username": share.user.username,
                        "can_edit": share.can_edit,
                    }
                )

    return requests


def get_public_requests(
    db: Session, skip: int = 0, limit: int = 100, developer_id: Optional[int] = None
):
    """Get public requests with optional developer filtering."""
    print(f"Getting public requests. Developer ID: {developer_id}")

    # Base query for public requests
    query = db.query(models.Request).filter(models.Request.is_public == True)

    if developer_id:
        print(f"Developer with ID {developer_id} is viewing requests")
        # You could add developer-specific logic here in the future
        # For example:
        # - Filtering by developer skills
        # - Excluding requests the developer has already responded to
        # - Showing only requests in certain categories

    requests = query.offset(skip).limit(limit).all()
    print(f"Found {len(requests)} requests")
    return requests


def get_request_by_id(db: Session, request_id: int):
    """Retrieve a specific request by its ID."""
    request = (
        db.query(models.Request)
        .join(models.User, models.Request.user_id == models.User.id)  # Join with User table
        .filter(models.Request.id == request_id)
        .first()
    )

    if request:
        # Add the owner's username to the request object
        owner = db.query(models.User).filter(models.User.id == request.user_id).first()
        setattr(request, "owner_username", owner.username if owner else "Unknown")

    return request


def update_request(
    db: Session, request_id: int, request_update: schemas.RequestUpdate, user_id: int
):
    """Update an existing request, ensuring edit permissions and checking for sensitive content."""
    db_request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not db_request:
        raise HTTPException(status_code=404, detail="Request not found")

    if not has_edit_permission(db, db_request, user_id):
        raise HTTPException(status_code=403, detail="Not authorized to edit this request")

    contains_sensitive = check_sensitive_content(request_update.content)
    if request_update.is_public and contains_sensitive:
        raise HTTPException(
            status_code=400, detail="Cannot make request public as it contains sensitive data"
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


def share_request(db: Session, request_id: int, user_id: int, share: schemas.RequestShare):
    """Share a request with another user, ensuring no sensitive data is shared."""
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to share this request")

    if request.contains_sensitive_data:
        raise HTTPException(
            status_code=400, detail="Cannot share requests containing sensitive data"
        )

    existing_share = (
        db.query(models.RequestShare)
        .filter(
            and_(
                models.RequestShare.request_id == request_id,
                models.RequestShare.shared_with_user_id == share.shared_with_user_id,
            )
        )
        .first()
    )

    if existing_share:
        raise HTTPException(status_code=400, detail="Request is already shared with this user")

    db_share = models.RequestShare(
        request_id=request_id,
        shared_with_user_id=share.shared_with_user_id,
        can_edit=share.can_edit,
    )
    db.add(db_share)
    db.commit()
    db.refresh(db_share)
    return db_share


def remove_share(db: Session, request_id: int, user_id: int, shared_user_id: int):
    """Remove sharing of a request for a specific user, ensuring ownership."""
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if request.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to modify sharing settings for this request"
        )

    share = (
        db.query(models.RequestShare)
        .filter(
            and_(
                models.RequestShare.request_id == request_id,
                models.RequestShare.shared_with_user_id == shared_user_id,
            )
        )
        .first()
    )

    if share:
        db.delete(share)
        db.commit()
    return share


def get_shared_requests(db: Session, user_id: int):
    """Get all requests shared with the user."""
    return (
        db.query(models.Request)
        .join(models.RequestShare, models.Request.id == models.RequestShare.request_id)
        .filter(models.RequestShare.shared_with_user_id == user_id)
        .all()
    )


def toggle_request_privacy(db: Session, request_id: int, user_id: int, is_public: bool):
    """Toggle the privacy of a request, ensuring ownership."""
    request = get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this request")

    request.is_public = is_public
    db.commit()
    db.refresh(request)
    return request


# Add these at the bottom of your crud_request.py file


def get_request_shares(db: Session, request_id: int):
    """
    Get all share information for a specific request, including user details.
    Returns a list of users who have access to the request.
    """
    shares = (
        db.query(models.RequestShare, models.User)
        .join(models.User, models.RequestShare.shared_with_user_id == models.User.id)
        .filter(models.RequestShare.request_id == request_id)
        .all()
    )

    result = []
    for share, user in shares:
        result.append(
            {
                "share_id": share.id,
                "user_id": user.id,
                "username": user.username,
                "can_edit": share.can_edit if hasattr(share, "can_edit") else False,
                "viewed_at": share.viewed_at,
                "created_at": share.created_at,
            }
        )

    return result


def is_request_shared_with_user(db: Session, request_id: int, user_id: int) -> bool:
    """
    Check if a request is shared with a specific user.
    """
    share = (
        db.query(models.RequestShare)
        .filter(
            and_(
                models.RequestShare.request_id == request_id,
                models.RequestShare.shared_with_user_id == user_id,
            )
        )
        .first()
    )
    return bool(share)


def add_request_to_project(db: Session, request_id: int, project_id: int, user_id: int):
    # Get the request and verify ownership
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this request")

    # Get the project and verify ownership
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to add to this project")

    # Get the owner's username
    owner = db.query(models.User).filter(models.User.id == request.user_id).first()

    # Update the request
    request.project_id = project_id
    request.added_to_project_at = datetime.utcnow()

    db.commit()
    db.refresh(request)

    # Add owner_username to the response
    setattr(request, "owner_username", owner.username)

    return request


def remove_request_from_project(db: Session, request_id: int, user_id: int):
    """Remove a request from its project."""
    request = get_request_by_id(db, request_id)
    if not request or request.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this request")

    request.project_id = None
    request.added_to_project_at = None
    db.commit()
    db.refresh(request)
    return request
