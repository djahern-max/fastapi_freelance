from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app import models, schemas
from typing import Optional, List
from fastapi import HTTPException
import re
from app.crud.crud_project import get_or_create_general_notes_project

def check_sensitive_content(content: str) -> bool:
    """Check if content contains sensitive information"""
    sensitive_patterns = [
        r'api[_-]key',
        r'password',
        r'secret',
        r'token',
        r'access[_-]key',
        r'private[_-]key',
        r'auth',
        r'credential'
    ]
    content_lower = content.lower()
    return any(re.search(pattern, content_lower) for pattern in sensitive_patterns)

def create_note(db: Session, note: schemas.NoteCreate, user_id: int):
    if note.project_id is None:
        general_project = get_or_create_general_notes_project(user_id=user_id, db=db)
        note.project_id = general_project.id
    
    contains_sensitive = check_sensitive_content(note.content)
    
    if note.is_public and contains_sensitive:
        raise HTTPException(status_code=400, detail="Cannot create public note with sensitive data")

    db_note = models.Note(
        **note.dict(),
        user_id=user_id,
        contains_sensitive_data=contains_sensitive
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


def get_notes(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Note).offset(skip).limit(limit).all()

def get_notes_by_user(
    db: Session, 
    user_id: int, 
    project_id: Optional[int] = None, 
    include_shared: bool = True,
    skip: int = 0, 
    limit: int = 100
):
    # Base query for user's notes
    query = db.query(models.Note)
    
    if project_id:
        query = query.filter(models.Note.project_id == project_id)
    
    if include_shared:
        query = query.filter(
            or_(
                models.Note.user_id == user_id,
                models.Note.id.in_(
                    db.query(models.NoteShare.note_id)
                    .filter(models.NoteShare.shared_with_user_id == user_id)
                )
            )
        )
    else:
        query = query.filter(models.Note.user_id == user_id)
    
    notes = query.offset(skip).limit(limit).all()
    
    # Format the shared_with information
    for note in notes:
        note.shared_with = [
            schemas.SharedUserInfo(
                user=schemas.UserBasic(
                    id=share.user.id,
                    username=share.user.username,
                    email=share.user.email
                ),
                can_edit=share.can_edit
            )
            for share in note.shared_with
        ]
    
    return notes


def get_public_notes(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Note)\
        .filter(models.Note.is_public == True)\
        .filter(models.Note.contains_sensitive_data == False)\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_note_by_id(db: Session, note_id: int):
    return db.query(models.Note).filter(models.Note.id == note_id).first()

def update_note(
    db: Session, 
    note_id: int, 
    note_update: schemas.NoteUpdate, 
    user_id: int
):
    db_note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Check if user has permission to edit
    if not has_edit_permission(db, db_note, user_id):
        raise HTTPException(status_code=403, detail="Not authorized to edit this note")
    
    # Check for sensitive data
    contains_sensitive = check_sensitive_content(note_update.content)
    
    # If note would become public but contains sensitive data, prevent update
    if note_update.is_public and contains_sensitive:
        raise HTTPException(
            status_code=400,
            detail="Cannot make note public as it contains sensitive data"
        )
    
    # Update the note
    for key, value in note_update.dict(exclude_unset=True).items():
        setattr(db_note, key, value)
    
    db_note.contains_sensitive_data = contains_sensitive
    db.commit()
    db.refresh(db_note)
    return db_note

def delete_note(db: Session, note_id: int, user_id: int):
    db_note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Only the owner can delete the note
    if db_note.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")
    
    db.delete(db_note)
    db.commit()
    return db_note

def share_note(
    db: Session, 
    note_id: int, 
    user_id: int, 
    share: schemas.NoteShare
):
    # Get the note
    note = get_note_by_id(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Verify ownership
    if note.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to share this note")
    
    # Check if note contains sensitive data
    if note.contains_sensitive_data:
        raise HTTPException(
            status_code=400,
            detail="Cannot share notes containing sensitive data"
        )
    
    # Check if share already exists
    existing_share = db.query(models.NoteShare).filter(
        and_(
            models.NoteShare.note_id == note_id,
            models.NoteShare.shared_with_user_id == share.shared_with_user_id
        )
    ).first()
    
    if existing_share:
        raise HTTPException(
            status_code=400,
            detail="Note is already shared with this user"
        )
    
    # Create new share
    db_share = models.NoteShare(
        note_id=note_id,
        shared_with_user_id=share.shared_with_user_id,
        can_edit=share.can_edit
    )
    db.add(db_share)
    db.commit()
    db.refresh(db_share)
    return db_share

def remove_share(
    db: Session, 
    note_id: int, 
    user_id: int, 
    shared_user_id: int
):
    # Get the note
    note = get_note_by_id(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Verify ownership
    if note.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to modify sharing settings for this note"
        )
    
    # Remove share
    share = db.query(models.NoteShare).filter(
        and_(
            models.NoteShare.note_id == note_id,
            models.NoteShare.shared_with_user_id == shared_user_id
        )
    ).first()
    
    if share:
        db.delete(share)
        db.commit()
    return share

def toggle_note_privacy(
    db: Session, 
    note_id: int, 
    user_id: int, 
    is_public: bool
):
    note = get_note_by_id(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to modify this note's privacy settings"
        )
    
    if is_public and note.contains_sensitive_data:
        raise HTTPException(
            status_code=400,
            detail="Cannot make notes containing sensitive data public"
        )
    
    note.is_public = is_public
    db.commit()
    db.refresh(note)
    return note

def has_edit_permission(db: Session, note: models.Note, user_id: int) -> bool:
    """Check if user has permission to edit a note"""
    # Owner always has edit permission
    if note.user_id == user_id:
        return True
    
    # Check if user has been granted edit permission through sharing
    share = db.query(models.NoteShare).filter(
        and_(
            models.NoteShare.note_id == note.id,
            models.NoteShare.shared_with_user_id == user_id,
            models.NoteShare.can_edit == True
        )
    ).first()
    
    return bool(share)

def search_users(db: Session, query: str, current_user_id: int, limit: int = 10):
    """Search users for sharing, excluding the current user"""
    return db.query(models.User)\
        .filter(
            and_(
                models.User.username.ilike(f"%{query}%"),
                models.User.id != current_user_id
            )
        )\
        .limit(limit)\
        .all()

def get_note_shares(db: Session, note_id: int):
    """Get all users a note is shared with"""
    return db.query(models.NoteShare)\
        .filter(models.NoteShare.note_id == note_id)\
        .all()




