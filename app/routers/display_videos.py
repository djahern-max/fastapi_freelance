import os
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import schemas, oauth2
from typing import List
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
from dotenv import load_dotenv
from app.database import get_db
from app.models import Video  # Assuming you have a Video model defined in models.py

load_dotenv()

# Initialize the logger
logger = logging.getLogger(__name__)

# Load environment variables
SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT = os.getenv('SPACES_ENDPOINT')
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_KEY = os.getenv('SPACES_KEY')
SPACES_SECRET = os.getenv('SPACES_SECRET')

# Initialize the boto3 client
s3_client = boto3.client('s3',
                         region_name=SPACES_REGION,
                         endpoint_url=SPACES_ENDPOINT,
                         aws_access_key_id=SPACES_KEY,
                         aws_secret_access_key=SPACES_SECRET,
                         config=Config(signature_version='s3v4'))


router = APIRouter(
    prefix="/video_display",
    tags=["Videos"]
)

async def get_videos_from_db(db: Session):
    # Fetch video and thumbnail paths from the database
    return db.query(Video).all()

# Function to download the thumbnail from Spaces
def download_thumbnail(file_name: str, local_path: str):
    try:
        logger.info(f"Attempting to download {file_name} from {SPACES_BUCKET}")
        s3_client.download_file(SPACES_BUCKET, file_name, local_path)
        logger.info(f"File downloaded successfully to {local_path}")
        return local_path
    except Exception as e:
        logger.error(f"Error downloading thumbnail: {str(e)}")
        raise HTTPException(status_code=500, detail="Error downloading thumbnail")


@router.get("/spaces", response_model=List[schemas.SpacesVideoInfo])
async def list_spaces_videos(current_user: schemas.User = Depends(oauth2.get_current_user), db: Session = Depends(get_db)):
    try:
        logger.info(f"Fetching video and thumbnail paths from the database")

        # Fetch video and thumbnail info from the database
        videos_from_db = await get_videos_from_db(db)

        videos = []
        
        for video in videos_from_db:
            videos.append({
                'filename': video.file_path.split('/')[-1],  # Extract filename from file_path
                # 'size': video.size,  # Comment this out if size is not available in the DB
                'last_modified': video.last_modified,  # Assuming last_modified is stored in the database
                'url': video.file_path,  # The video URL
                'thumbnail_path': video.thumbnail_path  # The thumbnail URL from DB
            })
        
        logger.info(f"Returning {len(videos)} video entries")
        return videos

    except Exception as e:
        logger.error(f"Error retrieving videos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving videos: {str(e)}")



# FastAPI route to download and serve the thumbnail
@router.get("/download_thumbnail/{thumbnail_filename}")
async def download_thumbnail_endpoint(thumbnail_filename: str):
    local_file_path = f"/tmp/{thumbnail_filename}"  # You can change the local path as needed

    try:
        # Call the function to download the thumbnail
        downloaded_file_path = download_thumbnail(thumbnail_filename, local_file_path)
        return {"message": f"File downloaded successfully", "file_path": downloaded_file_path}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Unexpected error occurred")
