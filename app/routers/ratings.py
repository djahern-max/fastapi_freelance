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
from ..models import ClientProfile, DeveloperProfile

router = APIRouter(prefix="/ratings", tags=["Ratings"])


# app/routers/ratings.py


@router.post("/developer/{developer_id}", response_model=RatingResponse)
async def rate_developer(
    developer_id: int,
    rating_data: DeveloperRatingCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Get developer profile
    developer = db.query(DeveloperProfile).filter(DeveloperProfile.user_id == developer_id).first()
    if not developer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Developer profile not found"
        )

    rating = rating_crud.create_or_update_rating(
        db,
        developer.id,  # Use developer profile ID
        current_user.id,  # Use current user's ID directly
        rating_data,
    )

    stats = rating_crud.get_developer_rating_stats(db, developer.id)

    return {
        "success": True,
        "average_rating": stats.average_rating,
        "total_ratings": stats.total_ratings,
        "message": "Rating updated successfully" if rating else "Rating added successfully",
    }


@router.get("/developer/{developer_id}", response_model=DeveloperRatingStats)
async def get_developer_rating(developer_id: int, db: Session = Depends(get_db)):
    developer = db.query(DeveloperProfile).filter(DeveloperProfile.user_id == developer_id).first()
    if not developer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Developer profile not found"
        )
    return rating_crud.get_developer_rating_stats(db, developer.id)


@router.get("/developer/{developer_id}/user-rating", response_model=Optional[DeveloperRatingOut])
async def get_user_rating(
    developer_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    developer = db.query(DeveloperProfile).filter(DeveloperProfile.user_id == developer_id).first()
    if not developer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Developer profile not found"
        )

    return rating_crud.get_user_rating(db, developer.id, current_user.id)


@router.get("/developer/{developer_id}/rating", response_model=DeveloperRatingStats)
async def get_developer_rating_by_user_id(developer_id: int, db: Session = Depends(get_db)):
    # First get the developer profile using the user_id
    developer = db.query(DeveloperProfile).filter(DeveloperProfile.user_id == developer_id).first()
    if not developer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Developer profile not found"
        )

    try:
        stats = rating_crud.get_developer_rating_stats(db, developer.id)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting developer rating: {str(e)}",
        )
