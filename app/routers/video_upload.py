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

# Load environment variables
ENV = os.getenv('ENV', 'local')
LOCAL_VIDEO_UPLOAD_DIR = os.getenv('LOCAL_VIDEO_UPLOAD_DIR', './videos')
SPACES_NAME = os.getenv('SPACES_NAME')
SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT = os.getenv('SPACES_ENDPOINT')
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_TOKEN = os.getenv('SPACES_TOKEN')

# Initialize the boto3 client for DigitalOcean Spaces (for production)
if ENV != 'local':
    s3 = boto3.client(
        's3',
        region_name=SPACES_REGION,
        endpoint_url=f"https://{SPACES_REGION}.digitaloceanspaces.com",
        aws_access_key_id=SPACES_TOKEN,
        aws_secret_access_key=SPACES_TOKEN
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
    db: Session = Depends(get_db),
    current_user: User = Depends(oauth2.get_current_user)
):
    if not current_user:
        logger.error("User authentication failed. No current user.")
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    logger.info(f"Current user ID: {current_user.id}")

    if not file.filename.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
        raise HTTPException(status_code=400, detail="Invalid video format")

    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    if ENV == 'local':
        # Save file locally
        local_file_path = os.path.join(LOCAL_VIDEO_UPLOAD_DIR, unique_filename)
        try:
            os.makedirs(LOCAL_VIDEO_UPLOAD_DIR, exist_ok=True)
            async with aiofiles.open(local_file_path, "wb") as buffer:
                while content := await file.read(1024 * 1024):  # 1 MB chunks
                    await buffer.write(content)
            file_url = f"/videos/{unique_filename}"
            logger.info(f"Uploaded video locally to: {local_file_path}")
        except IOError as e:
            logger.error(f"Failed to save video locally: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save video locally: {str(e)}")
    else:
        # Upload to DigitalOcean Spaces (production)
        try:
            s3.upload_fileobj(
                file.file,
                SPACES_BUCKET,
                unique_filename,
                ExtraArgs={'ACL': 'public-read'}
            )
            file_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{unique_filename}"
            logger.info(f"Uploaded video to Spaces: {file_url}")
        except NoCredentialsError:
            logger.error("Invalid Spaces credentials")
            raise HTTPException(status_code=500, detail="Invalid Spaces credentials")
        except Exception as e:
            logger.error(f"Failed to upload video to Spaces: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload video to Spaces: {str(e)}")

    try:
        new_video = Video(
            title=title,
            description=description,
            file_path=file_url,
            is_project=is_project,
            parent_project_id=parent_project_id,
            user_id=current_user.id
        )
        db.add(new_video)
        db.commit()
        db.refresh(new_video)
        logger.info(f"Video successfully uploaded by user {current_user.id}")
    except Exception as e:
        logger.error(f"Failed to create video entry in the database: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create video entry in the database")

    return new_video