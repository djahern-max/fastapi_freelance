import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from app import schemas, oauth2
from typing import List
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

# Initialize the logger
logger = logging.getLogger(__name__)

# Load environment variables
SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT = f"https://{SPACES_REGION}.digitaloceanspaces.com"
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_KEY = os.getenv('SPACES_KEY')
SPACES_SECRET = os.getenv('SPACES_SECRET')

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

def get_all_objects():
    objects = []
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=SPACES_BUCKET):
        if 'Contents' in page:
            objects.extend(page['Contents'])
    return objects

@router.get("/spaces", response_model=List[schemas.SpacesVideoInfo])
async def list_spaces_videos(current_user: schemas.User = Depends(oauth2.get_current_user)):
    try:
        logger.info(f"Listing objects in bucket: {SPACES_BUCKET}")
        
        objects = get_all_objects()
        
        videos = []
        thumbnails = []
        
        logger.info(f"Found {len(objects)} objects in the bucket")
        
        for item in objects:
            filename = item['Key']
            file_extension = os.path.splitext(filename)[1].lower()
            
            if file_extension in ['.mp4', '.avi', '.mov']:  # Video formats
                video_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{filename}"
                videos.append({
                    'filename': filename,
                    'size': item['Size'],
                    'last_modified': item['LastModified'],
                    'url': video_url,
                    'thumbnail_path': None
                })
                logger.info(f"Added video: {filename}")
            elif file_extension in ['.webp', '.jpg', '.png']:  # Thumbnail formats
                thumbnail_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{filename}"
                thumbnails.append({
                    'filename': filename,
                    'url': thumbnail_url
                })
                logger.info(f"Added thumbnail: {filename}")

        # Add thumbnail information to the response
        response = {
            'videos': videos,
            'thumbnails': thumbnails
        }

        logger.info(f"Returning {len(videos)} video entries and {len(thumbnails)} thumbnail entries")
        return response

    except ClientError as e:
        logger.error(f"Error listing objects from Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing objects: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.get("/thumbnail/{thumbnail_filename}")
async def get_thumbnail(thumbnail_filename: str):
    try:
        logger.info(f"Attempting to retrieve thumbnail: {thumbnail_filename}")

        try:
            s3.head_object(Bucket=SPACES_BUCKET, Key=thumbnail_filename)
            thumbnail_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{thumbnail_filename}"
            logger.info(f"Thumbnail found: {thumbnail_url}")
            return {"thumbnail_url": thumbnail_url}
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"Thumbnail not found: {thumbnail_filename}")
                return {"thumbnail_url": None}
            else:
                raise

    except Exception as e:
        logger.error(f"Error retrieving thumbnail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving thumbnail: {str(e)}")