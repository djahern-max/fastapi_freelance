# New file: app/crud/crud_playlist.py
from sqlalchemy.orm import Session
from .. import models, schemas
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func
from fastapi import HTTPException, status


def create_playlist(db: Session, playlist: schemas.PlaylistCreate, user_id: int):
    db_playlist = models.VideoPlaylist(
        name=playlist.name,
        description=playlist.description,
        creator_id=user_id,
        is_public=playlist.is_public,
    )
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    return db_playlist


def get_playlist(db: Session, playlist_id: int):
    # Get the playlist
    playlist = (
        db.query(models.VideoPlaylist)
        .filter(models.VideoPlaylist.id == playlist_id)
        .first()
    )

    if playlist:
        # Get all playlist videos with related video data
        playlist_videos = (
            db.query(models.PlaylistVideo)
            .filter(models.PlaylistVideo.playlist_id == playlist_id)
            .join(models.Video, models.Video.id == models.PlaylistVideo.video_id)
            .options(joinedload(models.PlaylistVideo.video))
            .order_by(models.PlaylistVideo.order)
            .all()
        )

        # Prepare the response with properly structured video data
        response = {
            "id": playlist.id,
            "name": playlist.name,
            "description": playlist.description,
            "is_public": playlist.is_public,
            "creator_id": playlist.creator_id,
            "created_at": playlist.created_at,
            # Transform videos into the format expected by frontend
            "videos": [
                {
                    "id": pv.video.id,
                    "title": pv.video.title,
                    "description": pv.video.description,
                    "thumbnail_path": pv.video.thumbnail_path,
                    "file_path": pv.video.file_path,
                    "order": pv.order,
                    "user_id": pv.video.user_id,
                    # Add other video fields needed by frontend
                }
                for pv in playlist_videos
            ],
        }

        # Get creator info if needed
        if hasattr(playlist, "creator") and playlist.creator:
            response["creator"] = {
                "id": playlist.creator.id,
                "username": playlist.creator.username,
            }

        return response

    return None


def get_playlists_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(models.VideoPlaylist)
        .filter(models.VideoPlaylist.creator_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def add_video_to_playlist(
    db: Session, playlist_id: int, video_id: int, order: Optional[int] = None
):
    try:
        # Check if video exists
        video = db.query(models.Video).filter(models.Video.id == video_id).first()
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
            )

        # Check if entry already exists
        existing = (
            db.query(models.PlaylistVideo)
            .filter(
                models.PlaylistVideo.playlist_id == playlist_id,
                models.PlaylistVideo.video_id == video_id,
            )
            .first()
        )

        if existing:
            # Update order if provided
            if order is not None:
                existing.order = order
                db.commit()
            return {
                "message": "Video already in playlist",
                "updated": order is not None,
            }

        # Calculate order if not provided
        if order is None:
            # Get the max order in the playlist
            max_order = (
                db.query(func.max(models.PlaylistVideo.order))
                .filter(models.PlaylistVideo.playlist_id == playlist_id)
                .scalar()
            )

            # Set order to max + 1, or 1 if no videos exist
            order = 1 if max_order is None else max_order + 1

        # Create new playlist video entry
        playlist_video = models.PlaylistVideo(
            playlist_id=playlist_id, video_id=video_id, order=order
        )

        db.add(playlist_video)
        db.commit()
        db.refresh(playlist_video)

        return {"message": "Video added to playlist successfully"}

    except SQLAlchemyError as e:
        db.rollback()
        # Log the error details for debugging
        print(f"Database error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add video to playlist due to database error",
        )
    except Exception as e:
        db.rollback()
        # Log general exceptions
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
