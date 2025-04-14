# New file: app/routers/playlists.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import schemas, models, oauth2
from ..database import get_db
from ..crud import crud_playlist

router = APIRouter(prefix="/playlists", tags=["playlists"])


@router.post("/", response_model=schemas.PlaylistResponse)
def create_playlist(
    playlist: schemas.PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    return crud_playlist.create_playlist(db, playlist, current_user.id)


@router.get("/{playlist_id}", response_model=schemas.PlaylistDetail)
def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    playlist = crud_playlist.get_playlist(db, playlist_id)
    if not playlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )
    return playlist


@router.get("/user/{user_id}", response_model=List[schemas.PlaylistResponse])
def get_user_playlists(
    user_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    return crud_playlist.get_playlists_by_user(db, user_id, skip, limit)


@router.post("/{playlist_id}/videos/{video_id}")
def add_video_to_playlist(
    playlist_id: int,
    video_id: int,
    order: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    # Verify ownership or permissions
    playlist = crud_playlist.get_playlist(db, playlist_id)
    if not playlist or playlist.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to modify this playlist",
        )

    return crud_playlist.add_video_to_playlist(db, playlist_id, video_id, order)
