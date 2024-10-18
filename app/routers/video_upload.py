from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app import models, schemas, database, oauth2
import boto3
import os
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(
    tags=["Videos"]
)

# Initialize S3 client
s3 = boto3.client('s3',
                  region_name=os.getenv('SPACES_REGION'),
                  endpoint_url=os.getenv('SPACES_ENDPOINT'),
                  aws_access_key_id=os.getenv('SPACES_KEY'),
                  aws_secret_access_key=os.getenv('SPACES_SECRET'))

@router.post("/upload", response_model=schemas.Video)
async def upload_video(
    title: str,
    description: str = None,
    is_project: bool = False,
    parent_project_id: int = None,
    video_file: UploadFile = File(...),
    thumbnail_file: UploadFile = File(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    # Upload video to DigitalOcean Spaces
    video_filename = f"{os.urandom(16).hex()}.mp4"
    video_url = f"https://{os.getenv('SPACES_NAME')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{video_filename}"
    
    try:
        s3.upload_fileobj(video_file.file, os.getenv('SPACES_BUCKET'), video_filename)
    except ClientError as e:
        raise HTTPException(status_code=500, detail="Failed to upload video")

    # Upload thumbnail if provided
    thumbnail_url = None
    if thumbnail_file:
        thumbnail_filename = f"{os.urandom(16).hex()}.webp"
        thumbnail_url = f"https://{os.getenv('SPACES_NAME')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{thumbnail_filename}"
        try:
            s3.upload_fileobj(thumbnail_file.file, os.getenv('SPACES_BUCKET'), thumbnail_filename)
        except ClientError as e:
            raise HTTPException(status_code=500, detail="Failed to upload thumbnail")

    # Create video entry in database
    new_video = models.Video(
        title=title,
        description=description,
        file_path=video_url,
        thumbnail_path=thumbnail_url,
        is_project=is_project,
        parent_project_id=parent_project_id,
        user_id=current_user.id
    )

    db.add(new_video)
    db.commit()
    db.refresh(new_video)

    return new_video