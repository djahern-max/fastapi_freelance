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
import uuid

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

@router.get("/spaces", response_model=List[schemas.SpacesVideoInfo])
async def list_spaces_videos(current_user: schemas.User = Depends(oauth2.get_current_user)):
    try:
        # List all objects in the bucket
        response = s3.list_objects_v2(Bucket=SPACES_BUCKET)
        
        videos = {}
        thumbnails = {}
        base_url = f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com"
        
        if 'Contents' in response:
            for item in response['Contents']:
                filename = item['Key']
                file_name, file_extension = os.path.splitext(filename)

                # Check if the filename (without extension) is a valid UUID
                try:
                    file_uuid = uuid.UUID(file_name)
                except ValueError:
                    continue  # Skip this file if it's not a valid UUID

                if file_extension.lower() in ['.mp4', '.avi', '.mov']:  # Video formats
                    videos[file_name] = {
                        'filename': filename,
                        'size': item['Size'],
                        'last_modified': item['LastModified'],
                        'url': f"{base_url}/{filename}",
                        'thumbnail_path': None
                    }
                elif file_extension.lower() in ['.webp', '.jpg', '.png']:  # Thumbnail formats
                    thumbnails[file_name] = f"{base_url}/{filename}"

        # Match thumbnails to videos
        for video_uuid, video_info in videos.items():
            for thumb_uuid, thumb_url in thumbnails.items():
                if thumb_uuid != video_uuid:  # Ensure we're not matching a video to itself
                    video_info['thumbnail_path'] = thumb_url
                    break  # Assign the first non-matching thumbnail and move to next video
            
            if video_info['thumbnail_path'] is None:
                # If no thumbnail was found, we could either leave it as None or assign a default
                video_info['thumbnail_path'] = "URL_TO_DEFAULT_THUMBNAIL"

        return list(videos.values())

    except ClientError as e:
        logger.error(f"Error listing videos from Spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing videos: {str(e)}")

@router.get("/stream/{video_id}")
async def stream_video(request: Request, video_id: int = Path(...), db: Session = Depends(database.get_db)):
    logger.info(f"Attempting to stream video with ID: {video_id}")
    try:
        video = get_video_by_id(video_id, db)
        logger.info(f"Video found: {video.title}, File path: {video.file_path}")

        is_spaces_video = video.file_path.startswith('https://')

        if is_spaces_video:
            # Streaming from Digital Ocean Spaces
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(video.file_path) as response:
                        if response.status != 200:
                            raise HTTPException(status_code=404, detail="Video file not found")
                        
                        headers = {
                            'Content-Type': response.headers.get('Content-Type', 'video/mp4'),
                            'Content-Length': response.headers.get('Content-Length', ''),
                            'Accept-Ranges': 'bytes',
                        }

                        return StreamingResponse(
                            response.content.iter_any(),
                            status_code=200,
                            headers=headers,
                        )
            except aiohttp.ClientError as e:
                logger.error(f"Error streaming from Spaces: {str(e)}")
                raise HTTPException(status_code=500, detail="Error streaming video from cloud storage")
        else:
            # Local file streaming (unchanged)
            if not os.path.exists(video.file_path):
                logger.error(f"Video file not found at path: {video.file_path}")
                raise HTTPException(status_code=404, detail="Video file not found")

            file_size = os.path.getsize(video.file_path)
            logger.info(f"Video file size: {file_size} bytes")
            
            range_header = request.headers.get('Range')

            start = 0
            end = file_size - 1

            if range_header:
                range_data = range_header.replace('bytes=', '').split('-')
                start = int(range_data[0])
                end = int(range_data[1]) if range_data[1] else file_size - 1

            chunk_size = 1024 * 1024  # 1MB chunks
            headers = {
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(end - start + 1),
                'Content-Type': 'video/mp4',
            }

            async def stream_generator():
                async with aiofiles.open(video.file_path, mode='rb') as video_file:
                    await video_file.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = await video_file.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            return StreamingResponse(
                stream_generator(),
                status_code=206 if range_header else 200,
                headers=headers,
            )

    except HTTPException as he:
        logger.error(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Error streaming video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")