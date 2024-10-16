import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from app import models, schemas, database, oauth2
import aiofiles
import aiohttp
from typing import List

# Initialize the logger
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/video_display",
    tags=["Videos"]
)

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
            # Local file streaming
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