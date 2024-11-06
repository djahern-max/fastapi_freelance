# app/crud/command_note.py
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional
from fastapi import HTTPException, status
from app import models
from app.schemas import CommandNoteCreate  # Make sure this import is correct

def create_command_note(db: Session, note: CommandNoteCreate, user_id: int):
    db_note = models.CommandNote(
        **note.dict(),
        user_id=user_id
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

def get_command_notes(db: Session, user_id: int, tag: Optional[str] = None):
    query = db.query(models.CommandNote).filter(models.CommandNote.user_id == user_id)
    if tag:
        query = query.filter(models.CommandNote.tags.contains([tag]))
    return query.all()  # Removed extra parenthesis

def get_command_note_by_id(
    db: Session, 
    note_id: int, 
    user_id: int
) -> models.CommandNote:
    note = db.query(models.CommandNote).filter(
        and_(
            models.CommandNote.id == note_id,
            models.CommandNote.user_id == user_id
        )
    ).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Command note with id {note_id} not found or you don't have access"
        )
    return note

def update_command_note(
    db: Session, 
    note_id: int, 
    note_update: CommandNoteCreate, 
    user_id: int
) -> models.CommandNote:
    try:
        db_note = get_command_note_by_id(db, note_id, user_id)
        
        update_data = note_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_note, key, value)
            
        db.commit()
        db.refresh(db_note)
        return db_note
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update command note: {str(e)}"
        )

def delete_command_note(
    db: Session, 
    note_id: int, 
    user_id: int
) -> models.CommandNote:
    try:
        db_note = get_command_note_by_id(db, note_id, user_id)
        db.delete(db_note)
        db.commit()
        return db_note
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete command note: {str(e)}"
        )
    
