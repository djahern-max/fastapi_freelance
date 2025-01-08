import os
import uuid
import boto3
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Video, VideoType
from app.schemas import VideoCreate
from botocore.exceptions import NoCredentialsError
from app import oauth2
from app.models import User
import logging
from typing import Optional

# Initialize the logger
logger = logging.getLogger(__name__)

# Load environment variables
SPACES_NAME = os.getenv("SPACES_NAME")
SPACES_REGION = os.getenv("SPACES_REGION")
SPACES_ENDPOINT = os.getenv("SPACES_ENDPOINT")
SPACES_BUCKET = os.getenv("SPACES_BUCKET")
SPACES_KEY = os.getenv("SPACES_KEY")
SPACES_SECRET = os.getenv("SPACES_SECRET")

# Initialize the boto3 client for DigitalOcean Spaces
s3 = boto3.client(
    "s3",
    region_name=SPACES_REGION,
    endpoint_url=SPACES_ENDPOINT,
    aws_access_key_id=SPACES_KEY,
    aws_secret_access_key=SPACES_SECRET,
)

router = APIRouter(prefix="/videos", tags=["Videos"])


@router.post("/")
async def upload_video(
    title: str = Form(...),
    description: str = Form(None),
    project_id: int = Form(None),
    request_id: int = Form(None),
    video_type: VideoType = Form(VideoType.solution_demo),
    file: UploadFile = File(...),
    thumbnail: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(oauth2.get_current_user),
):
    try:
        # Log initial request details
        logger.info(f"Starting video upload for user {current_user.id}")
        logger.info(
            f"File details - Filename: {file.filename}, Content-Type: {file.content_type}"
        )
        if thumbnail:
            logger.info(
                f"Thumbnail details - Filename: {thumbnail.filename}, Content-Type: {thumbnail.content_type}"
            )

        # Verify DO Spaces configuration
        spaces_config = {
            "bucket": os.getenv("SPACES_BUCKET"),
            "region": os.getenv("SPACES_REGION"),
            "endpoint": os.getenv("SPACES_ENDPOINT"),
            "key_exists": bool(os.getenv("SPACES_KEY")),
            "secret_exists": bool(os.getenv("SPACES_SECRET")),
        }
        logger.info(f"DO Spaces Configuration: {spaces_config}")

        # Read file content with error handling
        try:
            file_content = await file.read()
            if not file_content:
                raise ValueError("File content is empty")
            logger.info(
                f"Successfully read file content, size: {len(file_content)} bytes"
            )
        except Exception as e:
            logger.error(f"Error reading file content: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

        # Initialize S3 client
        try:
            s3 = boto3.client(
                "s3",
                region_name=os.getenv("SPACES_REGION"),
                endpoint_url=os.getenv("SPACES_ENDPOINT"),
                aws_access_key_id=os.getenv("SPACES_KEY"),
                aws_secret_access_key=os.getenv("SPACES_SECRET"),
            )
            logger.info("Successfully initialized S3 client")
        except Exception as e:
            logger.error(f"Error initializing S3 client: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"S3 client initialization failed: {str(e)}"
            )

        # Generate unique filename and upload video
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        logger.info(f"Generated unique filename: {unique_filename}")

        # Upload video to DO Spaces
        try:
            s3.put_object(
                Bucket=os.getenv("SPACES_BUCKET"),
                Key=unique_filename,
                Body=file_content,
                ACL="public-read",
                ContentType="video/mp4",
            )
            logger.info("Successfully uploaded video to DO Spaces")
        except Exception as e:
            logger.error(f"Error uploading video to DO Spaces: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Upload to DO Spaces failed: {str(e)}"
            )

        file_url = f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{unique_filename}"
        logger.info(f"Generated video URL: {file_url}")

        # Handle thumbnail upload if provided
        thumbnail_path = None
        if thumbnail:
            try:
                logger.info("Starting thumbnail upload")
                thumbnail_content = await thumbnail.read()

                if not thumbnail_content:
                    logger.error("Thumbnail content is empty")
                    raise ValueError("Thumbnail content is empty")

                thumbnail_extension = os.path.splitext(thumbnail.filename)[1]
                unique_thumbnail_filename = f"{uuid.uuid4()}{thumbnail_extension}"

                # Set content type based on file extension
                content_type = (
                    "image/webp"
                    if thumbnail_extension.lower() == ".webp"
                    else "image/jpeg"
                )

                logger.info(
                    f"Uploading thumbnail with filename: {unique_thumbnail_filename}"
                )
                s3.put_object(
                    Bucket=os.getenv("SPACES_BUCKET"),
                    Key=unique_thumbnail_filename,
                    Body=thumbnail_content,
                    ACL="public-read",
                    ContentType=content_type,
                )

                thumbnail_path = f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{unique_thumbnail_filename}"
                logger.info(f"Thumbnail uploaded successfully: {thumbnail_path}")

            except Exception as e:
                logger.error(f"Error uploading thumbnail: {str(e)}")
                logger.warning("Continuing without thumbnail due to upload error")

        # Save to database
        try:
            new_video = Video(
                title=title,
                description=description,
                file_path=file_url,
                thumbnail_path=thumbnail_path,
                project_id=project_id,
                request_id=request_id,
                user_id=current_user.id,
                video_type=video_type,
            )
            db.add(new_video)
            db.commit()
            db.refresh(new_video)
            logger.info(f"Successfully saved video to database with ID: {new_video.id}")

            return new_video
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error in upload_video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Reset file positions
        await file.seek(0)
        if thumbnail:
            await thumbnail.seek(0)


@router.post("/{video_id}/share")
async def generate_share_link(
    video_id: int,
    project_url: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(oauth2.get_current_user),
):
    # Get the video
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Update project URL if provided
    if project_url:
        video.project_url = project_url

    # Generate share token if not exists
    if not video.share_token:
        video.share_token = str(uuid.uuid4())

    video.is_public = True
    db.commit()

    base_url = (
        "https://www.ryze.ai"
        if os.getenv("ENV") == "production"
        else "http://localhost:3000"
    )
    share_url = f"{base_url}/shared/videos/{video.share_token}"

    return {"share_url": share_url, "project_url": video.project_url}
