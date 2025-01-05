from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Video
from typing import Optional

router = APIRouter(prefix="/shared/videos", tags=["Shared Videos"])


@router.get("/{share_token}")
def get_shared_video(share_token: str, db: Session = Depends(get_db)):
    video = (
        db.query(Video)
        .filter(Video.share_token == share_token, Video.is_public == True)
        .first()
    )

    if not video:
        raise HTTPException(
            status_code=404, detail="Video not found or is no longer shared"
        )

    # Return direct DO Spaces URL for the video
    return {
        "id": video.id,
        "title": video.title,
        "description": video.description,
        "file_path": video.file_path,  # This will be the DO Spaces URL
        "thumbnail_path": video.thumbnail_path,
        "project_url": video.project_url,
        "upload_date": video.upload_date,
    }
