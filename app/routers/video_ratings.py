# /app/routers/video_ratings.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas, oauth2
from ..database import get_db
from ..crud.video_rating import video_rating  # Import the instance instead of functions

router = APIRouter(prefix="/videos", tags=["video-ratings"])


@router.post("/{video_id}/rating", response_model=schemas.VideoRatingResponse)
def rate_video(
    video_id: int,
    rating: schemas.VideoRatingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    # Check if video exists
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Create or update rating using the CRUD class instance
    rating_obj = video_rating.create_or_update_video_rating(
        db=db, video_id=video_id, user_id=current_user.id, rating_data=rating
    )

    # Get updated stats
    stats = video_rating.get_video_rating_stats(db, video_id)

    return {
        "success": True,
        "average_rating": stats["average_rating"],
        "total_ratings": stats["total_ratings"],
        "message": "Rating submitted successfully",
    }


@router.get("/{video_id}/rating", response_model=schemas.VideoRatingStats)
def get_video_ratings(video_id: int, db: Session = Depends(get_db)):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    stats = video_rating.get_video_rating_stats(db, video_id)
    return {
        "average_rating": stats["average_rating"],
        "total_ratings": stats["total_ratings"],
    }


@router.get("/{video_id}/user-rating", response_model=schemas.VideoRating)
def get_user_video_rating(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    rating = video_rating.get_user_rating(db, video_id, current_user.id)
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    return rating
