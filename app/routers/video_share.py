from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Video
from app.config import settings  # Import the settings
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
    project_url: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
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
        db.refresh(video)  # Make sure to refresh

    # Return just the token
    return {"share_token": video.share_token}
