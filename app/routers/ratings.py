from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..oauth2 import get_current_user
from ..crud import rating as rating_crud
from ..schemas import (
    DeveloperRatingCreate,
    DeveloperRatingOut,
    DeveloperRatingStats,
    RatingResponse,
)
from ..models import ClientProfile

router = APIRouter(prefix="/ratings", tags=["Ratings"])


@router.post("/developer/{developer_id}", response_model=RatingResponse)
async def rate_developer(
    developer_id: int,
    rating_data: DeveloperRatingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Verify the current user is a client
    client = db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    if not client:
        raise HTTPException(status_code=403, detail="Only clients can rate developers")

    # Create or update rating
    rating = rating_crud.create_or_update_rating(db, developer_id, client.id, rating_data)

    # Get updated stats
    stats = rating_crud.get_developer_rating_stats(db, developer_id)

    return {
        "success": True,
        "average_rating": stats.average_rating,
        "total_ratings": stats.total_ratings,
        "message": "Rating updated successfully" if rating else "Rating added successfully",
    }


@router.get("/developer/{developer_id}", response_model=DeveloperRatingStats)
async def get_developer_rating(developer_id: int, db: Session = Depends(get_db)):
    return rating_crud.get_developer_rating_stats(db, developer_id)


@router.get("/developer/{developer_id}/user-rating", response_model=Optional[DeveloperRatingOut])
async def get_user_rating(
    developer_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    client = db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    if not client:
        return None

    return rating_crud.get_user_rating(db, developer_id, client.id)
