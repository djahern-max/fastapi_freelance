import os
import uuid
import aiofiles
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

# Load environment variables from .env
ENV = os.getenv('ENV', 'local')
LOCAL_VIDEO_UPLOAD_DIR = os.getenv('LOCAL_VIDEO_UPLOAD_DIR', './videos')
SPACES_NAME = os.getenv('SPACES_NAME')
SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT = os.getenv('SPACES_ENDPOINT')
SPACES_TOKEN = os.getenv('SPACES_TOKEN')

# Initialize the boto3 client for DigitalOcean Spaces (for production)
s3 = boto3.client(
    's3',
    region_name=SPACES_REGION,
    endpoint_url=SPACES_ENDPOINT,
    aws_access_key_id=SPACES_TOKEN,
    aws_secret_access_key=SPACES_TOKEN
)

# Initialize the router
router = APIRouter(
    prefix="/videos",
    tags=["Videos"]
)

# Ensure the local video directory exists (for local testing)
if ENV == 'local':
    os.makedirs(LOCAL_VIDEO_UPLOAD_DIR, exist_ok=True)

@router.post("/", response_model=VideoCreate)
async def upload_video(
    title: str = Form(...),
    description: str = Form(None),
    is_project: bool = Form(False),
    parent_project_id: int = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(oauth2.get_current_user)  # User authentication
):
    # Log the current user for debugging purposes
    if not current_user:
        logger.error("User authentication failed. No current user.")
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    logger.info(f"Current user ID: {current_user.id}")

    # Validate file type
    if not file.filename.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
        raise HTTPException(status_code=400, detail="Invalid video format")

    # Generate a unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    # Handle file upload based on the environment
    if ENV == 'local':
        # Save file locally
        local_file_path = os.path.join(LOCAL_VIDEO_UPLOAD_DIR, unique_filename)
        try:
            async with aiofiles.open(local_file_path, "wb") as buffer:
                chunk_size = 1024 * 1024  # 1 MB chunks
                while content := await file.read(chunk_size):
                    await buffer.write(content)
            # Store the relative path (remove 'file://')
            file_url = f"./videos/{unique_filename}"
        except IOError as e:
            logger.error(f"Failed to save video locally: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save video locally: {str(e)}")
    
    else:
        # Upload to DigitalOcean Spaces (production)
        try:
            s3.upload_fileobj(
                file.file,
                SPACES_NAME,
                unique_filename,
                ExtraArgs={'ACL': 'public-read'}  # Make the file publicly accessible
            )
            # Generate the public URL for the uploaded file
            file_url = f"https://{SPACES_NAME}.{SPACES_REGION}.digitaloceanspaces.com/{unique_filename}"
        except NoCredentialsError:
            logger.error("Invalid Spaces credentials")
            raise HTTPException(status_code=500, detail="Invalid Spaces credentials")
        except Exception as e:
            logger.error(f"Failed to upload video to Spaces: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload video to Spaces: {str(e)}")

    # Save video metadata to the database
    try:
        new_video = Video(
            title=title,
            description=description,
            file_path=file_url,  # Store the file URL (local or Spaces)
            is_project=is_project,
            parent_project_id=parent_project_id,
            user_id=current_user.id  # Pass the current user ID here
        )
        db.add(new_video)
        db.commit()
        db.refresh(new_video)
        logger.info(f"Video successfully uploaded by user {current_user.id}")
    except Exception as e:
        logger.error(f"Failed to create video entry in the database: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create video entry in the database")

    return new_video
