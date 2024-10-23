from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..oauth2 import get_current_user
from app import schemas, crud

router = APIRouter()

# Create a new project
@router.post("/", response_model=schemas.ProjectOut)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(get_db), current_user: int = Depends(get_current_user)):
    return crud.crud_project.create_project(db=db, project=project, user_id=current_user.id)

# Get all projects for the current user
@router.get("/", response_model=list[schemas.ProjectOut])
def get_projects(db: Session = Depends(get_db), current_user: int = Depends(get_current_user)):
    return crud.crud_project.get_projects_by_user(db=db, user_id=current_user.id)
