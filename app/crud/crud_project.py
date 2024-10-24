from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app import models, schemas
from typing import List

def create_project(db: Session, project: schemas.ProjectCreate, user_id: int) -> models.Project:
    try:
        db_project = models.Project(
            name=project.name,
            description=project.description,
            user_id=user_id
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )

def get_projects_by_user(db: Session, user_id: int) -> List[models.Project]:
    try:
        return db.query(models.Project).filter(models.Project.user_id == user_id).all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch projects: {str(e)}"
        )

def get_project(db: Session, project_id: int) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found"
        )
    return project

def get_project_by_id_and_user(db: Session, project_id: int, user_id: int) -> models.Project:
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == user_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found or you don't have access"
        )
    return project

def update_project(db: Session, project_id: int, project_update: schemas.ProjectUpdate, user_id: int) -> models.Project:
    try:
        db_project = get_project_by_id_and_user(db, project_id, user_id)
        
        update_data = project_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_project, key, value)
            
        db.commit()
        db.refresh(db_project)
        return db_project
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}"
        )

def delete_project(db: Session, project_id: int, user_id: int) -> models.Project:
    try:
        db_project = get_project_by_id_and_user(db, project_id, user_id)
        db.delete(db_project)
        db.commit()
        return db_project
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )

# This function was indented incorrectly, so now it is at the correct level
def get_or_create_general_notes_project(user_id: int, db: Session):
    project = db.query(models.Project).filter(models.Project.user_id == user_id, models.Project.name == "General Notes").first()
    if not project:
        # Create the "General Notes" project if it doesn't exist
        new_project = models.Project(name="General Notes", description="Default project for unassigned notes", user_id=user_id)
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return new_project
    return project
