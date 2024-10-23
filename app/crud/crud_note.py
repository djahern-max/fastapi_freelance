from sqlalchemy.orm import Session
from app import models, schemas
from typing import Optional

def create_note(db: Session, note: schemas.NoteCreate, user_id: int):
    db_note = models.Note(**note.dict(), user_id=user_id)
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


def get_notes(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Note).offset(skip).limit(limit).all()

def get_notes_by_user(db: Session, user_id: int, project_id: Optional[int] = None, skip: int = 0, limit: int = 10):
    query = db.query(models.Note).filter(models.Note.user_id == user_id)
    if project_id:
        query = query.filter(models.Note.project_id == project_id)  # Filter by project_id
    return query.offset(skip).limit(limit).all()


def get_note_by_id(db: Session, note_id: int):
    return db.query(models.Note).filter(models.Note.id == note_id).first()

def update_note(db: Session, note_id: int, note: schemas.NoteUpdate):
    db_note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if db_note:
        for key, value in note.dict(exclude_unset=True).items():
            setattr(db_note, key, value)
        db.commit()
        db.refresh(db_note)
    return db_note

def delete_note(db: Session, note_id: int):
    db_note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if db_note:
        db.delete(db_note)
        db.commit()
    return db_note
