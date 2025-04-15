from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Video
import secrets
import string

router = APIRouter(prefix="/videos", tags=["Videos"])


def generate_share_token(length=10):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/{video_id}/share")
def generate_share_link(video_id: int, db: Session = Depends(get_db)):
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
        video.is_public = True
        db.commit()

    # Return just the token - let the frontend build the full URL
    return {"share_token": video.share_token}
