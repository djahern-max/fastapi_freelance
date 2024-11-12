from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.crud import crud_request, crud_user
from app import schemas, models
from app.models import UserType
from ..database import get_db
from ..oauth2 import get_current_user, get_optional_user

router = APIRouter(prefix="/requests", tags=["Requests"])

# ------------------ Shared and Public Requests ------------------

@router.get("/shared-with-me", response_model=List[schemas.SimpleRequestOut])
def get_shared_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all requests shared with the current user."""
    if current_user.user_type != UserType.DEVELOPER:
        raise HTTPException(status_code=403, detail="Only developers can access shared requests")
    return crud_request.get_shared_requests(db=db, user_id=current_user.id)

@router.get("/public", response_model=List[schemas.RequestOut])
def get_public_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_user)
):
    """Get all public requests, optionally filtering for developer-specific results."""
    try:
        developer_id = current_user.id if current_user and current_user.user_type.lower() == UserType.DEVELOPER.lower() else None
        requests = crud_request.get_public_requests(db=db, skip=skip, limit=limit, developer_id=developer_id)
        # Return empty list if no requests found
        return requests if requests else []
    except Exception as e:
        print(f"Error fetching public requests: {str(e)}")
        # Return empty list instead of throwing 500 error
        return []

# ------------------ CRUD Operations ------------------

@router.post("/", response_model=schemas.RequestOut)
def create_request(
    request: schemas.RequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new request, restricted to clients."""
    if current_user.user_type != UserType.CLIENT:
        raise HTTPException(status_code=403, detail="Only clients can create requests")
    return crud_request.create_request(db=db, request=request, user_id=current_user.id)

@router.get("/", response_model=List[schemas.SimpleRequestOut])
def get_requests(
    project_id: Optional[int] = None,
    include_shared: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Retrieve all requests for the current user."""
    if current_user.user_type != UserType.CLIENT:
        raise HTTPException(status_code=403, detail="Only clients can access their requests")
    return crud_request.get_requests_by_user(
        db=db,
        user_id=current_user.id,
        project_id=project_id,
        include_shared=include_shared,
        skip=skip,
        limit=limit
    )

@router.get("/{request_id}", response_model=schemas.RequestOut)
def read_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific request."""
    request = crud_request.get_request_by_id(db=db, request_id=request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    if request.user_id != current_user.id and not request.is_public:
        shares = crud_request.get_request_shares(db=db, request_id=request_id)
        if not any(share.shared_with_user_id == current_user.id for share in shares):
            raise HTTPException(status_code=403, detail="Not authorized to access this request")
    
    return request

@router.put("/{request_id}", response_model=schemas.RequestOut)
def update_request(
    request_id: int,
    request: schemas.RequestUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update a request, ensuring only clients have update permissions."""
    if current_user.user_type != UserType.CLIENT:
        raise HTTPException(status_code=403, detail="Only clients can update requests")
    return crud_request.update_request(
        db=db,
        request_id=request_id,
        request_update=request,
        user_id=current_user.id
    )

@router.delete("/{request_id}", status_code=status.HTTP_200_OK)
def delete_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a request, limited to the owner."""
    if current_user.user_type != UserType.CLIENT:
        raise HTTPException(status_code=403, detail="Only clients can delete requests")
    return crud_request.delete_request(db=db, request_id=request_id, user_id=current_user.id)

# ------------------ Sharing Functionality ------------------

@router.get("/{request_id}/shares/users", response_model=List[schemas.UserBasic])
def get_request_shares(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all users that a request is shared with."""
    request = crud_request.get_request_by_id(db=db, request_id=request_id)
    if not request or request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view shares")
    return crud_request.get_request_shares(db=db, request_id=request_id)

@router.post("/{request_id}/share", response_model=schemas.RequestShareResponse)
def share_request(
    request_id: int,
    share: schemas.RequestShare,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Share a request with another user."""
    if current_user.user_type != UserType.CLIENT:
        raise HTTPException(status_code=403, detail="Only clients can share requests")
    return crud_request.share_request(db=db, request_id=request_id, user_id=current_user.id, share=share)

@router.delete("/{request_id}/share/{user_id}", status_code=status.HTTP_200_OK)
def remove_share(
    request_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Remove request sharing for a specific user."""
    if current_user.user_type != UserType.CLIENT:
        raise HTTPException(status_code=403, detail="Only clients can modify request shares")
    return crud_request.remove_share(db=db, request_id=request_id, user_id=current_user.id, shared_user_id=user_id)

# ------------------ User Search ------------------

@router.get("/users/search", response_model=List[schemas.UserBasic])
def search_users(
    q: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Search users by username prefix."""
    if current_user.user_type == UserType.CLIENT:
        return crud_user.search_developers(db=db, username_prefix=q)
    else:
        return crud_user.search_clients(db=db, username_prefix=q)

@router.get("/search/users", response_model=List[schemas.UserBasic])
def search_users_alt(
    query: str,
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Alternative endpoint for user search (keeping for backward compatibility)."""
    if current_user.user_type == UserType.CLIENT:
        return crud_user.search_developers(db=db, username_prefix=query, limit=limit)
    else:
        return crud_user.search_clients(db=db, username_prefix=query, limit=limit)

# ------------------ Privacy Control ------------------

@router.put("/{request_id}/privacy", response_model=schemas.RequestOut)
def update_request_privacy(
    request_id: int,
    is_public: bool,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Toggle a request's public/private status."""
    if current_user.user_type != UserType.CLIENT:
        raise HTTPException(status_code=403, detail="Only clients can modify request privacy")
    return crud_request.toggle_request_privacy(db=db, request_id=request_id, user_id=current_user.id, is_public=is_public)
