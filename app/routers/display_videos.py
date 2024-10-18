import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from app import models, schemas, database, oauth2
import aiofiles
import aiohttp
from typing import List
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv() 

# Initialize the logger
logger = logging.getLogger(__name__)

# Load environment variables
SPACES_NAME = os.getenv('SPACES_NAME')
SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT = f"https://{SPACES_REGION}.digitaloceanspaces.com"
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_KEY = os.getenv('SPACES_KEY')
SPACES_SECRET = os.getenv('SPACES_SECRET')

##This updated Mo FO!!!!!!!!!

print(f"SPACES_NAME: {SPACES_NAME}")
print(f"SPACES_REGION: {SPACES_REGION}")
print(f"SPACES_BUCKET: {SPACES_BUCKET}")
print(f"SPACES_KEY: {SPACES_KEY}")
print(f"SPACES_SECRET: {SPACES_SECRET}")

router = APIRouter(
    prefix="/video_display",
    tags=["Videos"]
)

# Initialize the boto3 client
s3 = boto3.client('s3',
                  region_name=SPACES_REGION,
                  endpoint_url=SPACES_ENDPOINT,
                  aws_access_key_id=SPACES_KEY,
                  aws_secret_access_key=SPACES_SECRET)

def get_video_by_id(video_id: int, db: Session):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

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
        raise HTTPException(status_code=500, detail="Internal server error")

import logging

logger = logging.getLogger(__name__)

from botocore.client import Config

@router.get("/spaces", response_model=List[schemas.SpacesVideoInfo])
async def list_spaces_videos(current_user: schemas.User = Depends(oauth2.get_current_user)):
    try:
        logger.info(f"Listing video objects in bucket: {SPACES_BUCKET}")
        
        # Create S3 client
        s3_client = boto3.client('s3',
                                 region_name=SPACES_REGION,
                                 endpoint_url=SPACES_ENDPOINT,
                                 aws_access_key_id=SPACES_KEY,
                                 aws_secret_access_key=SPACES_SECRET,
                                 config=Config(signature_version='s3v4'))

        # List all video objects in the bucket
        response = s3_client.list_objects_v2(Bucket=SPACES_BUCKET)

        videos = []
        
        if 'Contents' in response:
            for item in response['Contents']:
                filename = item['Key']
                file_extension = os.path.splitext(filename)[1].lower()
                
                if file_extension in ['.mp4', '.avi', '.mov']:  # Only process video files
                    videos.append({
                        'filename': filename,
                        'size': item['Size'],
                        'last_modified': item['LastModified'],
                        'url': f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{filename}"
                    })

        logger.info(f"Returning {len(videos)} video entries")
        return videos

    except ClientError as e:
        logger.error(f"Error listing videos from Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing videos: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.get("/thumbnail/{video_name}")
async def get_thumbnail(video_name: str, db: Session = Depends(database.get_db)):
    try:
        # Fetch the video by its name and retrieve the thumbnail_path from the model
        video = db.query(models.Video).filter(models.Video.file_path.like(f"%{video_name}%")).first()
        
        if video and video.thumbnail_path:
            logger.info(f"Thumbnail found for video: {video_name}")
            return {"thumbnail_url": video.thumbnail_path}
        else:
            logger.warning(f"No thumbnail found for video: {video_name}")
            raise HTTPException(status_code=404, detail="Thumbnail not found")

    except Exception as e:
        logger.error(f"Error retrieving thumbnail: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving thumbnail")

