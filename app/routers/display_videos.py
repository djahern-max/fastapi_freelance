from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import models, schemas, database, oauth2
from typing import List

# Import your schemas correctly
from app.schemas import VideoResponse

router = APIRouter(
    prefix="/video_display",
    tags=["Videos"]
)

@router.get("/", response_model=schemas.VideoResponse)
def display_videos(
    db: Session = Depends(database.get_db), 
    current_user: models.User = Depends(oauth2.get_current_user)
):
    # Fetch videos for the logged-in user
    user_videos = db.query(models.Video).filter(models.Video.user_id == current_user.id).all()
    
    # Fetch videos from other users
    other_videos = db.query(models.Video).filter(models.Video.user_id != current_user.id).all()

    return schemas.VideoResponse(user_videos=user_videos, other_videos=other_videos)
