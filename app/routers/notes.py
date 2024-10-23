from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..oauth2 import get_current_user
from app.crud import crud_note
from app import schemas
from typing import List
from app.crud import crud_project

router = APIRouter()

@router.post("/", response_model=schemas.NoteOut)
def create_note(note: schemas.NoteCreate, db: Session = Depends(get_db), current_user: int = Depends(get_current_user)):
    return crud_note.create_note(db=db, note=note, user_id=current_user.id)

@router.get("/", response_model=List[schemas.ProjectOut])
def get_projects(db: Session = Depends(get_db), current_user: int = Depends(get_current_user)):
    projects = crud_project.get_projects_by_user(db=db, user_id=current_user.id)
    return projects or []  # Return an empty list if no projects exist


@router.get("/{note_id}", response_model=schemas.NoteOut)
def read_note(note_id: int, db: Session = Depends(get_db), current_user: int = Depends(get_current_user)):
    note = crud_note.get_note_by_id(db=db, note_id=note_id)
    if note is None or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Note not found or access denied")
    return note

@router.put("/{note_id}", response_model=schemas.NoteOut)
def update_note(note_id: int, note: schemas.NoteUpdate, db: Session = Depends(get_db)):
    return crud_note.update_note(db=db, note_id=note_id, note=note)

@router.delete("/{note_id}", response_model=schemas.NoteOut)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    return crud_note.delete_note(db=db, note_id=note_id)
