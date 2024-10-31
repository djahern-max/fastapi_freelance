from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from fastapi import HTTPException
import re
from app import models, schemas
from app.crud.crud_project import get_or_create_general_notes_project

# ------------------ Utility Functions ------------------

def check_sensitive_content(content: str) -> bool:
    """Check if content contains sensitive information."""
    sensitive_patterns = [
        r'api[_-]key', r'password', r'secret', r'token', 
        r'access[_-]key', r'private[_-]key', r'auth', r'credential'
    ]
    content_lower = content.lower()
    return any(re.search(pattern, content_lower) for pattern in sensitive_patterns)

def has_edit_permission(db: Session, note: models.Note, user_id: int) -> bool:
    """Check if a user has permission to edit a note."""
    if note.user_id == user_id:
        return True
    share = db.query(models.NoteShare).filter(
        and_(
            models.NoteShare.note_id == note.id,
            models.NoteShare.shared_with_user_id == user_id,
            models.NoteShare.can_edit == True
        )
    ).first()
    return bool(share)

# ------------------ CRUD Operations ------------------

def create_note(db: Session, note: schemas.NoteCreate, user_id: int):
    """Create a new note, assigning it to 'General Notes' if no project ID is provided."""
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
    """Retrieve all notes with optional pagination."""
    return db.query(models.Note).offset(skip).limit(limit).all()

def get_notes_by_user(
    db: Session,
    user_id: int,
    project_id: Optional[int] = None,
    include_shared: bool = True,
    skip: int = 0,
    limit: int = 100
):
    """Get notes for a specific user with optional project filtering."""
    # Start with user's own notes
    query = db.query(models.Note)
    
    if project_id:
        query = query.filter(models.Note.project_id == project_id)
    
    # Filter for user's own notes
    own_notes = query.filter(models.Note.user_id == user_id)
    
    if include_shared:
        # Get notes shared with the user
        shared_notes_query = db.query(models.Note).join(
            models.NoteShare, 
            models.Note.id == models.NoteShare.note_id
        ).filter(models.NoteShare.shared_with_user_id == user_id)
        
        if project_id:
            shared_notes_query = shared_notes_query.filter(models.Note.project_id == project_id)
        
        # Combine own notes and shared notes
        query = own_notes.union(shared_notes_query)
    else:
        query = own_notes
    
    # Apply pagination and get notes
    notes = query.offset(skip).limit(limit).all()
    
    # Convert notes to dictionary representation
    result = []
    for note in notes:
        # Get all shares for this note
        shares = db.query(models.NoteShare).join(
            models.User, 
            models.NoteShare.shared_with_user_id == models.User.id
        ).filter(
            models.NoteShare.note_id == note.id
        ).all()
        
        # Convert note to dict and add shares
        note_dict = {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "project_id": note.project_id,
            "user_id": note.user_id,
            "is_public": note.is_public,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "contains_sensitive_data": note.contains_sensitive_data,
            "shared_with": [
                {
                    "user_id": share.shared_with_user_id,
                    "username": db.query(models.User)
                        .filter(models.User.id == share.shared_with_user_id)
                        .first().username,
                    "can_edit": share.can_edit
                }
                for share in shares
            ]
        }
        result.append(note_dict)
    
    return result

def get_public_notes(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all public notes without sensitive data."""
    return db.query(models.Note)\
        .filter(models.Note.is_public == True)\
        .filter(models.Note.contains_sensitive_data == False)\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_note_by_id(db: Session, note_id: int):
    """Retrieve a specific note by its ID."""
    return db.query(models.Note).filter(models.Note.id == note_id).first()

def update_note(
    db: Session, 
    note_id: int, 
    note_update: schemas.NoteUpdate, 
    user_id: int
):
    """Update an existing note, checking for edit permissions and sensitive content."""
    db_note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if not has_edit_permission(db, db_note, user_id):
        raise HTTPException(status_code=403, detail="Not authorized to edit this note")
    
    contains_sensitive = check_sensitive_content(note_update.content)
    if note_update.is_public and contains_sensitive:
        raise HTTPException(
            status_code=400,
            detail="Cannot make note public as it contains sensitive data"
        )
    
    for key, value in note_update.dict(exclude_unset=True).items():
        setattr(db_note, key, value)
    
    db_note.contains_sensitive_data = contains_sensitive
    db.commit()
    db.refresh(db_note)
    return db_note

def delete_note(db: Session, note_id: int, user_id: int):
    """Delete a note, ensuring only the owner can delete it."""
    # Get the note and eagerly load the shared_with relationship
    db_note = db.query(models.Note)\
        .filter(models.Note.id == note_id)\
        .first()
    
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if db_note.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")
    
    # Delete associated shares first
    db.query(models.NoteShare)\
        .filter(models.NoteShare.note_id == note_id)\
        .delete()
    
    # Delete the note
    db.delete(db_note)
    db.commit()
    
    return {"message": "Note deleted successfully"}

# ------------------ Sharing Functionality ------------------

def share_note(
    db: Session, 
    note_id: int, 
    user_id: int, 
    share: schemas.NoteShare
):
    """Share a note with another user, ensuring ownership and no sensitive data."""
    note = get_note_by_id(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to share this note")
    
    if note.contains_sensitive_data:
        raise HTTPException(
            status_code=400,
            detail="Cannot share notes containing sensitive data"
        )
    
    existing_share = db.query(models.NoteShare).filter(
        and_(
            models.NoteShare.note_id == note_id,
            models.NoteShare.shared_with_user_id == share.shared_with_user_id
        )
    ).first()
    
    if existing_share:
        raise HTTPException(status_code=400, detail="Note is already shared with this user")
    
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
    """Remove sharing of a note for a specific user, ensuring ownership."""
    note = get_note_by_id(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    if note.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to modify sharing settings for this note"
        )
    
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

# In crud_note.py, add this function:

def get_shared_notes(db: Session, user_id: int):
    """Get all notes that have been shared with the user."""
    shared_notes = (
        db.query(models.Note)
        .join(models.NoteShare, models.Note.id == models.NoteShare.note_id)
        .filter(models.NoteShare.shared_with_user_id == user_id)
        .all()
    )
    
    result = []
    for note in shared_notes:
        # Get the owner's username
        owner = db.query(models.User).filter(models.User.id == note.user_id).first()
        
        shares = db.query(models.NoteShare).join(
            models.User, 
            models.NoteShare.shared_with_user_id == models.User.id
        ).filter(
            models.NoteShare.note_id == note.id
        ).all()
        
        note_dict = {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "project_id": note.project_id,
            "user_id": note.user_id,
            "owner_username": owner.username,  # Added this line
            "is_public": note.is_public,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "contains_sensitive_data": note.contains_sensitive_data,
            "shared_with": [
                {
                    "user_id": share.shared_with_user_id,
                    "username": db.query(models.User)
                        .filter(models.User.id == share.shared_with_user_id)
                        .first().username,
                    "can_edit": share.can_edit
                }
                for share in shares
            ]
        }
        result.append(note_dict)
    
    return result
# ------------------ Privacy Control ------------------

def toggle_note_privacy(
    db: Session, 
    note_id: int, 
    user_id: int, 
    is_public: bool
):
    """Toggle the privacy status of a note."""
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

# ------------------ User Search ------------------

def search_users(db: Session, query: str, current_user_id: int, limit: int = 10):
    """Search users for sharing, excluding the current user."""
    return db.query(models.User)\
        .filter(
            and_(
                models.User.username.ilike(f"%{query}%"),
                models.User.id != current_user_id
            )
        )\
        .limit(limit)\
        .all()


