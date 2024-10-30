from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.crud import crud_note
from app import schemas
from app.models import Project
from app.crud.crud_project import get_or_create_general_notes_project
from app.schemas import SimpleNoteOut
from ..database import get_db
from ..oauth2 import get_current_user

router = APIRouter(
    prefix="/notes",
    tags=["Notes"]
)

# ------------------ CRUD Operations ------------------

@router.post("/", response_model=schemas.NoteOut)
def create_note(
    note: schemas.NoteCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Create a new note."""
    if note.project_id is None:
        general_notes_project = get_or_create_general_notes_project(user_id=current_user.id, db=db)
        note.project_id = general_notes_project.id

    return crud_note.create_note(db=db, note=note, user_id=current_user.id)

@router.get("/", response_model=List[SimpleNoteOut])
def get_notes(
    project_id: Optional[int] = None,
    include_shared: bool = True,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Get all notes for the current user."""
    return crud_note.get_notes_by_user(
        db=db,
        user_id=current_user.id,
        project_id=project_id,
        include_shared=include_shared,
        skip=skip,
        limit=limit
    )

@router.get("/public", response_model=List[schemas.NoteOut])
def get_public_notes(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, le=100),
    db: Session = Depends(get_db)
):
    """Get all public notes."""
    return crud_note.get_public_notes(db=db, skip=skip, limit=limit)

@router.get("/{note_id}", response_model=schemas.NoteOut)
def read_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Get a specific note."""
    note = crud_note.get_note_by_id(db=db, note_id=note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.user_id != current_user.id and not note.is_public:
        shares = crud_note.get_note_shares(db=db, note_id=note_id)
        if not any(share.shared_with_user_id == current_user.id for share in shares):
            raise HTTPException(status_code=403, detail="Not authorized to access this note")
    
    return note

@router.put("/{note_id}", response_model=schemas.NoteOut)
def update_note(
    note_id: int,
    note: schemas.NoteUpdate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Update a note."""
    return crud_note.update_note(
        db=db,
        note_id=note_id,
        note_update=note,
        user_id=current_user.id
    )

@router.delete("/{note_id}", response_model=schemas.NoteOut)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Delete a note."""
    return crud_note.delete_note(db=db, note_id=note_id, user_id=current_user.id)

# ------------------ Sharing Functionality ------------------

@router.post("/{note_id}/share", response_model=schemas.NoteShareResponse)
def share_note(
    note_id: int,
    share: schemas.NoteShare,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Share a note with another user."""
    return crud_note.share_note(
        db=db,
        note_id=note_id,
        user_id=current_user.id,
        share=share
    )

@router.delete("/{note_id}/share/{user_id}")
def remove_share(
    note_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Remove note sharing for a specific user."""
    return crud_note.remove_share(
        db=db,
        note_id=note_id,
        user_id=current_user.id,
        shared_user_id=user_id
    )

@router.get("/{note_id}/shares", response_model=List[schemas.NoteShareResponse])
def get_note_shares(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Get all users a note is shared with."""
    note = crud_note.get_note_by_id(db=db, note_id=note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view share information for this note"
        )
    
    return crud_note.get_note_shares(db=db, note_id=note_id)

# ------------------ Privacy Control ------------------

@router.put("/{note_id}/privacy")
def update_note_privacy(
    note_id: int,
    is_public: bool,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Toggle a note's public/private status."""
    return crud_note.toggle_note_privacy(
        db=db,
        note_id=note_id,
        user_id=current_user.id,
        is_public=is_public
    )

# ------------------ User Search ------------------

@router.get("/search/users", response_model=List[schemas.UserBasic])
def search_users(
    query: str,
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    """Search users for sharing."""
    return crud_note.search_users(
        db=db,
        query=query,
        current_user_id=current_user.id,
        limit=limit
    )
