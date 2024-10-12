import logging
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from app import models, schemas, database, oauth2
import os
import aiofiles

# Initialize the logger
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/video_display",
    tags=["Videos"]
)

@router.get("/", response_model=schemas.VideoResponse)
def display_videos(
    db: Session = Depends(database.get_db), 
    current_user: models.User = Depends(oauth2.get_current_user)
):
    try:
        # Fetch videos for the logged-in user
        user_videos = db.query(models.Video).filter(models.Video.user_id == current_user.id).all()
        
        # Fetch videos from other users
        other_videos = db.query(models.Video).filter(models.Video.user_id != current_user.id).all()

        # Log the video data
        logger.info(f"User videos: {[{v.id, v.title} for v in user_videos]}")
        logger.info(f"Other videos: {[{v.id, v.title} for v in other_videos]}")

        return schemas.VideoResponse(user_videos=user_videos, other_videos=other_videos)

    except Exception as e:
        logger.error(f"Error retrieving videos: {str(e)}")
        raise

def get_video_by_id(video_id: int, db: Session):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

async def iterfile(path):
    """Async generator to stream video file in chunks."""
    try:
        async with aiofiles.open(path, mode='rb') as f:
            while chunk := await f.read(1024 * 1024):  # Read in 1MB chunks
                yield chunk
    except Exception as e:
        logger.error(f"Error reading video file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error reading video file")

@router.get("/stream/{video_id}")
async def stream_video(video_id: int = Path(...), db: Session = Depends(database.get_db)):
    logger.info(f"Attempting to stream video with ID: {video_id}")
    try:
        video = get_video_by_id(video_id, db)
        logger.info(f"Video found: {video.title}, File path: {video.file_path}")
        
        if not os.path.exists(video.file_path):
            logger.error(f"Video file not found at path: {video.file_path}")
            raise HTTPException(status_code=404, detail="Video file not found")
        
        file_size = os.path.getsize(video.file_path)
        logger.info(f"Video file size: {file_size} bytes")
        
        # Stream video file with the appropriate media type (MP4)
        return StreamingResponse(iterfile(video.file_path), media_type="video/mp4")
    except HTTPException as he:
        logger.error(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error streaming video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
