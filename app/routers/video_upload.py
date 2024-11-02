import os
import uuid
import boto3
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Video
from app.schemas import VideoCreate
from botocore.exceptions import NoCredentialsError
from app import oauth2
from app.models import User
import logging

# Initialize the logger
logger = logging.getLogger(__name__)

# Load environment variables
SPACES_NAME = os.getenv('SPACES_NAME')
SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT = os.getenv('SPACES_ENDPOINT')
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_KEY = os.getenv('SPACES_KEY')
SPACES_SECRET = os.getenv('SPACES_SECRET')

# Initialize the boto3 client for DigitalOcean Spaces
s3 = boto3.client(
    's3',
    region_name=SPACES_REGION,
    endpoint_url=SPACES_ENDPOINT,
    aws_access_key_id=SPACES_KEY,
    aws_secret_access_key=SPACES_SECRET
)

router = APIRouter(
    prefix="/videos",
    tags=["Videos"]
)

@router.post("/", response_model=VideoCreate)
async def upload_video(
    title: str = Form(...),
    description: str = Form(None),
    is_project: bool = Form(False),
    parent_project_id: int = Form(None),
    file: UploadFile = File(...),
    thumbnail: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(oauth2.get_current_user)
):
    if not current_user:
        logger.error("User authentication failed. No current user.")
        raise HTTPException(status_code=401, detail="User not authenticated")

    logger.info(f"Current user ID: {current_user.id}")

    # Validate video file format
    if not file.filename.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
        raise HTTPException(status_code=400, detail="Invalid video format")

    try:
        # Generate unique filename and upload video
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_content = await file.read()
        
        s3.put_object(
            Bucket=SPACES_BUCKET,
            Key=unique_filename,
            Body=file_content,
            ACL='public-read'
        )
        
        file_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{unique_filename}"
        logger.info(f"Uploaded video to Spaces: {file_url}")

        # Handle thumbnail if provided
        thumbnail_path = None
        if thumbnail:
            thumbnail_extension = os.path.splitext(thumbnail.filename)[1]
            unique_thumbnail_filename = f"{uuid.uuid4()}{thumbnail_extension}"
            thumbnail_content = await thumbnail.read()
            
            s3.put_object(
                Bucket=SPACES_BUCKET,
                Key=unique_thumbnail_filename,
                Body=thumbnail_content,
                ACL='public-read'
            )
            
            thumbnail_path = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{unique_thumbnail_filename}"
            logger.info(f"Uploaded thumbnail to Spaces: {thumbnail_path}")

        # Save video info to database
        new_video = Video(
            title=title,
            description=description,
            file_path=file_url,
            thumbnail_path=thumbnail_path,
            is_project=is_project,
            parent_project_id=parent_project_id,
            user_id=current_user.id
        )
        db.add(new_video)
        db.commit()
        db.refresh(new_video)
        logger.info(f"Video successfully uploaded by user {current_user.id}")
        
        return new_video

    except NoCredentialsError:
        logger.error("Invalid Spaces credentials")
        raise HTTPException(status_code=500, detail="Invalid Spaces credentials")
    except Exception as e:
        logger.error(f"Failed to upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")