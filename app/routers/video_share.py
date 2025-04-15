from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Video
import secrets
import string
from typing import Optional
from app import oauth2
from app import models

router = APIRouter(prefix="/videos", tags=["Videos"])


def generate_share_token(length=10):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/{video_id}/share")
def generate_share_link(
    video_id: int,
    project_url: Optional[str] = None,  # Add optional project URL
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),  # Ensure authentication
):
    # First check if the video exists and if the user has permission
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
        )

    # Verify ownership
    if video.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to share this video",
        )

    # Generate a unique share token if none exists
    if not video.share_token:
        while True:
            share_token = generate_share_token()
            existing = db.query(Video).filter(Video.share_token == share_token).first()
            if not existing:
                break

        video.share_token = share_token

        # Store project URL if provided
        if project_url:
            video.project_url = project_url

        video.is_public = True
        db.commit()
        db.refresh(video)  # Refresh to ensure we have the updated video

    # Return token - frontend can construct full URL if needed
    return {"share_token": video.share_token}
