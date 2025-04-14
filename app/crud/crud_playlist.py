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
    # Get the playlist with eager loading
    playlist = (
        db.query(models.VideoPlaylist)
        .options(
            joinedload(models.VideoPlaylist.creator),
            joinedload(models.VideoPlaylist.videos).joinedload(
                models.PlaylistVideo.video
            ),
        )
        .filter(models.VideoPlaylist.id == playlist_id)
        .first()
    )

    if playlist:
        # Transform the data if needed for your schema
        # For example, if your schema expects a 'videos' field with direct video objects
        video_list = []
        for playlist_video in sorted(playlist.videos, key=lambda pv: pv.order):
            video_list.append(
                {
                    "id": playlist_video.video.id,
                    "title": playlist_video.video.title,
                    "thumbnail_path": playlist_video.video.thumbnail_path,
                    "order": playlist_video.order,
                    # Add other fields as needed by your schema
                }
            )

        # Attach the transformed data if your schema expects it
        playlist.formatted_videos = video_list

    return playlist


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
