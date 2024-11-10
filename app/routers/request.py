from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.crud import crud_request, crud_user
from app import schemas
from app.models import RequestShare, User
from app.crud.crud_project import get_or_create_general_requests_project
from ..database import get_db
from ..oauth2 import get_current_user

router = APIRouter(
    prefix="/requests",
    tags=["Requests"]
)

# Make sure this route is BEFORE any routes with path parameters (like /{request_id})
@router.get("/shared-with-me", response_model=List[schemas.SimpleRequestOut])
def get_shared_requests(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Get all requests shared with the current user."""
    return crud_request.get_shared_requests(db=db, user_id=current_user.id)

@router.get("/requests/{request_id}/shares/users")
async def get_request_shares(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get all users that the request is shared with
    shares = db.query(RequestShare).filter(RequestShare.request_id == request_id).all()
    shared_users = [
        {
            "id": share.shared_with_user_id,
            "username": share.shared_with_user.username
        }
        for share in shares
    ]
    return shared_users

@router.get("/public-requests", response_model=List[schemas.RequestOut])
def get_public_requests(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    db: Session = Depends(get_db)
):
    """Retrieve all public requests."""
    return crud_request.get_public_requests(db=db, skip=skip, limit=limit)

# ------------------ CRUD Operations ------------------

# routers/requests.py
@router.post("/", response_model=schemas.RequestOut)
def create_request(
    request: schemas.RequestCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Create a new request."""
    return crud_request.create_request(db=db, request=request, user_id=current_user.id)

@router.get("/", response_model=List[schemas.SimpleRequestOut])
def get_requests(
    project_id: Optional[int] = None,
    include_shared: bool = True,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Get all requests for the current user."""
    return crud_request.get_requests_by_user(
        db=db,
        user_id=current_user.id,
        project_id=project_id,
        include_shared=include_shared,
        skip=skip,
        limit=limit
    )

@router.get("/public", response_model=List[schemas.RequestOut])
def get_public_requests(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    db: Session = Depends(get_db)
):
    """Get all public requests."""
    return crud_request.get_public_requests(db=db, skip=skip, limit=limit)

@router.get("/{request_id}", response_model=schemas.RequestOut)
def read_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
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
    current_user: schemas.User = Depends(get_current_user)
):
    """Update a request."""
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
    current_user: schemas.User = Depends(get_current_user)
):
    """Delete a request."""
    return crud_request.delete_request(db=db, request_id=request_id, user_id=current_user.id)

# ------------------ Sharing Functionality ------------------

@router.post("/{request_id}/share", response_model=schemas.RequestShareResponse)
def share_request(
    request_id: int,
    share: schemas.RequestShare,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Share a request with another user."""
    return crud_request.share_request(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
        share=share
    )

@router.delete("/{request_id}/share/{user_id}")
def remove_share(
    request_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Remove request sharing for a specific user."""
    return crud_request.remove_share(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
        shared_user_id=user_id
    )

@router.get("/users/search")
def search_users(
    q: str,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Search users by username prefix."""
    return crud_user.search_users(db=db, username_prefix=q)

# ------------------ Privacy Control ------------------

@router.put("/{request_id}/privacy")
def update_request_privacy(
    request_id: int,
    is_public: bool,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Toggle a request's public/private status."""
    return crud_request.toggle_request_privacy(
        db=db,
        request_id=request_id,
        user_id=current_user.id,
        is_public=is_public
    )

# ------------------ User Search ------------------

@router.get("/search/users", response_model=List[schemas.UserBasic])
def search_users(
    query: str,
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Search users for sharing."""
    return crud_request.search_users(
        db=db,
        query=query,
        current_user_id=current_user.id,
        limit=limit
    )




