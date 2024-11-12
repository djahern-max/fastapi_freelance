from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app import models, schemas
from typing import List

def create_project(db: Session, project: schemas.ProjectCreate, user_id: int) -> models.Project:
    # Check if user is a client
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user.user_type != models.UserType.client:  # Using lowercase
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can create projects"
        )

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
    # Check user type
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user.user_type != models.UserType.client:  # Changed from CLIENT to client
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can access projects"
        )

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

# Refactored function to use "General Requests" project
def get_or_create_general_requests_project(user_id: int, db: Session):
    project = db.query(models.Project).filter(models.Project.user_id == user_id, models.Project.name == "General Requests").first()
    if not project:
        # Create the "General Requests" project if it doesn't exist
        new_project = models.Project(name="General Requests", description="Default project for unassigned requests", user_id=user_id)
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return new_project
    return project

# Check if a project has any associated requests
def check_project_has_requests(db: Session, project_id: int) -> bool:
    """Check if a project has any associated requests."""
    request_count = db.query(models.Request).filter(models.Request.project_id == project_id).count()
    return request_count > 0

def delete_project(db: Session, project_id: int, user_id: int) -> models.Project:
    try:
        db_project = get_project_by_id_and_user(db, project_id, user_id)
        
        # Check if project has requests
        if check_project_has_requests(db, project_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete project that contains requests. Please delete all requests first."
            )
        
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
    
def get_project(db: Session, project_id: int) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found"
        )
    return project
