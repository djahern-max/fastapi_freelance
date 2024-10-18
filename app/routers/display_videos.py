from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas, database, oauth2
from typing import List

router = APIRouter(
    prefix="/video_display",
    tags=["Videos"]
)

@router.get("/", response_model=List[schemas.Video])
async def list_videos(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    videos = db.query(models.Video).filter(models.Video.user_id == current_user.id).all()
    return videos

@router.get("/{video_id}", response_model=schemas.Video)
async def get_video(
    video_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    video = db.query(models.Video).filter(models.Video.id == video_id, models.Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.get("/thumbnail/{video_name}")
async def get_thumbnail(video_name: str, db: Session = Depends(database.get_db)):
    try:
        # Fetch the video by its name and retrieve the thumbnail_path from the model
        video = db.query(models.Video).filter(models.Video.file_path.like(f"%{video_name}%")).first()
        
        if video and video.thumbnail_path:
            return {"thumbnail_url": video.thumbnail_path}
        else:
            raise HTTPException(status_code=404, detail="Thumbnail not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error retrieving thumbnail")