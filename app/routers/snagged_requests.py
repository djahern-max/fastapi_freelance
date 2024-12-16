# app/routers/snagged_requests.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from .. import models, schemas, database, oauth2
from ..middleware import require_active_subscription
from ..schemas import SnaggedRequestWithDetails


router = APIRouter(prefix="/snagged-requests", tags=["Snagged Requests"])


@router.get("/", response_model=List[SnaggedRequestWithDetails])
def get_snagged_requests(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(status_code=403, detail="Only developers can view snagged requests")

    # Get snagged requests with full request and user information
    snagged_requests = (
        db.query(models.SnaggedRequest)
        .join(models.Request, models.SnaggedRequest.request_id == models.Request.id)
        .join(models.User, models.Request.user_id == models.User.id)
        .filter(
            models.SnaggedRequest.developer_id == current_user.id,
            models.SnaggedRequest.is_active == True,
        )
        .with_entities(
            models.SnaggedRequest, models.Request, models.User.username.label("owner_username")
        )
        .all()
    )

    # Format the response
    result = []
    for snagged, request, owner_username in snagged_requests:
        result.append(
            {
                "id": snagged.id,
                "request_id": snagged.request_id,
                "developer_id": snagged.developer_id,
                "snagged_at": snagged.snagged_at,
                "is_active": snagged.is_active,
                "request": {
                    "id": request.id,
                    "title": request.title,
                    "content": request.content,
                    "status": request.status,
                    "estimated_budget": request.estimated_budget,
                    "owner_username": owner_username,
                },
            }
        )

    return result


@router.get("/", response_model=List[schemas.SnaggedRequestOut])
def get_snagged_requests(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(status_code=403, detail="Only developers can view snagged requests")

    snagged_requests = (
        db.query(models.SnaggedRequest)
        .filter(
            models.SnaggedRequest.developer_id == current_user.id,
            models.SnaggedRequest.is_active == True,
        )
        .all()
    )

    return snagged_requests


@router.delete("/{request_id}", status_code=status.HTTP_200_OK)
def remove_snagged_request(
    request_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    snagged_request = (
        db.query(models.SnaggedRequest)
        .filter(
            models.SnaggedRequest.request_id == request_id,
            models.SnaggedRequest.developer_id == current_user.id,
        )
        .first()
    )

    if not snagged_request:
        raise HTTPException(status_code=404, detail="Snagged request not found")

    snagged_request.is_active = False
    db.commit()
    return {"message": "Request removed from snagged list"}
