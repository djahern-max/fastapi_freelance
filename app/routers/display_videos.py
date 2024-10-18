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

@router.get("/videos", response_model=List[schemas.SpacesVideoInfo])
async def list_videos(current_user: schemas.User = Depends(oauth2.get_current_user)):
    try:
        logger.info(f"Listing video objects in bucket: {SPACES_BUCKET}")
        
        response = s3.list_objects_v2(Bucket=SPACES_BUCKET)
        
        videos = []
        
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
                        'url': video_url
                    })
                    logger.info(f"Added video: {filename}")

        logger.info(f"Returning {len(videos)} video entries")
        return videos

    except ClientError as e:
        logger.error(f"Error listing videos from Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing videos: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.get("/images", response_model=List[schemas.SpacesImageInfo])
async def list_images(current_user: schemas.User = Depends(oauth2.get_current_user)):
    try:
        logger.info(f"Listing image objects in bucket: {SPACES_BUCKET}")
        
        response = s3.list_objects_v2(Bucket=SPACES_BUCKET)
        
        images = []
        
        if 'Contents' in response:
            logger.info(f"Found {len(response['Contents'])} objects in the bucket")
            
            for item in response['Contents']:
                filename = item['Key']
                file_extension = os.path.splitext(filename)[1].lower()
                
                if file_extension in ['.jpg', '.png', '.webp']:  # Image formats
                    image_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{filename}"
                    images.append({
                        'filename': filename,
                        'url': image_url
                    })
                    logger.info(f"Added image: {filename}")

        logger.info(f"Returning {len(images)} image entries")
        return images

    except ClientError as e:
        logger.error(f"Error listing images from Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing images: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.get("/image/{image_filename}")
async def get_image(image_filename: str):
    """
    Retrieve the image by its filename.
    """

    try:
        # Check if the image exists in the bucket
        s3.head_object(Bucket=SPACES_BUCKET, Key=image_filename)
        
        # If the image exists, generate and return the URL
        image_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{image_filename}"
        return {"image_url": image_url}

    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            raise HTTPException(status_code=404, detail="Image not found")
        else:
            logger.error(f"Error accessing image: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error accessing image: {str(e)}")
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")