import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from app import schemas, oauth2
from typing import List
import boto3
from botocore.exceptions import ClientError
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

def get_thumbnail_path(video_name):
    thumbnail_extensions = ['.webp', '.jpg', '.png']
    
    for ext in thumbnail_extensions:
        thumbnail_filename = f"{video_name}{ext}"
        try:
            s3.head_object(Bucket=SPACES_BUCKET, Key=thumbnail_filename)
            return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{thumbnail_filename}"
        except ClientError:
            continue
    
    return None

@router.get("/spaces", response_model=List[schemas.SpacesVideoInfo])
async def list_spaces_videos(current_user: schemas.User = Depends(oauth2.get_current_user)):
    try:
        logger.info(f"Listing objects in bucket: {SPACES_BUCKET}")
        
        response = s3.list_objects_v2(Bucket=SPACES_BUCKET)
        
        videos = []
        images = []
        
        if 'Contents' in response:
            logger.info(f"Found {len(response['Contents'])} objects in the bucket")
            
            for item in response['Contents']:
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
                elif file_extension in ['.jpg', '.png', '.webp']:  # Image formats
                    image_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{filename}"
                    images.append({
                        'filename': filename,
                        'url': image_url
                    })
                    logger.info(f"Added image: {filename}")

        logger.info(f"Returning {len(videos)} video entries and {len(images)} image entries")
        return {"videos": videos, "images": images}

    except ClientError as e:
        logger.error(f"Error listing objects from Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing objects: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    
@router.get("/thumbnail/{thumbnail_filename}")
async def get_thumbnail(thumbnail_filename: str):
    """
    Retrieve the thumbnail (image) by its filename, without assuming any association with a video.
    """

    try:
        # Ensure the filename includes the extension
        valid_extensions = ['.webp', '.jpg', '.png']
        if not any(thumbnail_filename.endswith(ext) for ext in valid_extensions):
            raise HTTPException(status_code=400, detail="Invalid file extension. Only .webp, .jpg, and .png are allowed.")
        
        # Check if the thumbnail exists in the bucket
        s3.head_object(Bucket=SPACES_BUCKET, Key=thumbnail_filename)
        
        # If the thumbnail exists, generate and return the URL
        thumbnail_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{thumbnail_filename}"
        return {"thumbnail_url": thumbnail_url}

    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        else:
            logger.error(f"Error accessing thumbnail: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error accessing thumbnail: {str(e)}")
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")