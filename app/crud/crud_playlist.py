# New file: app/crud/crud_playlist.py
from sqlalchemy.orm import Session
from .. import models, schemas
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import joinedload


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
    # Get the maximum order if not provided
    if order is None:
        max_order = (
            db.query(func.max(models.PlaylistVideo.order))
            .filter(models.PlaylistVideo.playlist_id == playlist_id)
            .scalar()
            or 0
        )
        order = max_order + 1

    # Create the relationship
    db_playlist_video = models.PlaylistVideo(
        playlist_id=playlist_id, video_id=video_id, order=order
    )

    db.add(db_playlist_video)
    db.commit()
    return db_playlist_video
