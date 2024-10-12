import aiofiles
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Video
from app.schemas import VideoCreate
import uuid
from fastapi.responses import StreamingResponse, FileResponse
import os
import logging


# Initialize the logger
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/videos",
    tags=["Videos"]
)

# Use an absolute path for VIDEO_UPLOAD_DIR
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_videos")

# Ensure the upload directory exists
os.makedirs(VIDEO_UPLOAD_DIR, exist_ok=True)

# Helper function to get a video by id
def get_video_by_id(video_id: int, db: Session):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.post("/", response_model=VideoCreate)
async def upload_video(
    title: str = Form(...),  # Change to Form
    description: str = Form(None),  # Change to Form
    is_project: bool = Form(False),  # Change to Form
    parent_project_id: int = Form(None),  # Change to Form
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Validate file type
    if not file.filename.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
        raise HTTPException(status_code=400, detail="Invalid video format")

    # Generate a unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_location = os.path.join(VIDEO_UPLOAD_DIR, unique_filename)

    # Save the file asynchronously
    try:
        async with aiofiles.open(file_location, "wb") as buffer:
            # Read the file in chunks to handle large files
            chunk_size = 1024 * 1024  # 1 MB chunks
            while content := await file.read(chunk_size):
                await buffer.write(content)
    except IOError as e:
        logger.error(f"Failed to save video file: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save video file")

    # Create a new video entry in the database
    try:
        new_video = Video(
            title=title,
            description=description,
            file_path=file_location,
            is_project=is_project,
            parent_project_id=parent_project_id
        )
        db.add(new_video)
        db.commit()
        db.refresh(new_video)
    except Exception as e:
        # If database operation fails, delete the uploaded file
        logger.error(f"Failed to create video entry in the database: {str(e)}")
        os.remove(file_location)
        raise HTTPException(status_code=500, detail="Failed to create video entry")

    return new_video

