from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app import models, schemas
from typing import List


def create_project(db: Session, project: schemas.ProjectCreate, user_id: int):
    """Create a project as an optional grouping mechanism."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user.user_type != models.UserType.client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only clients can create projects"
        )

    db_project = models.Project(
        name=project.name, description=project.description, user_id=user_id, is_active=True
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


# In crud_project.py


def get_projects_by_user(db: Session, user_id: int) -> List[models.Project]:
    try:
        # Get projects with related requests and their conversations
        projects = db.query(models.Project).filter(models.Project.user_id == user_id).all()

        for project in projects:
            # Get all requests for this project
            requests = (
                db.query(models.Request).filter(models.Request.project_id == project.id).all()
            )

            # Get all conversations for the project's requests
            conversation_counts = (
                db.query(models.Conversation)
                .filter(models.Conversation.request_id.in_([r.id for r in requests]))
                .all()
            )

            # Add computed fields to project
            project.request_stats = {
                "total": len(requests),
                "open": len([r for r in requests if r.status == "open"]),
                "completed": len([r for r in requests if r.status == "completed"]),
                "total_budget": sum(r.estimated_budget or 0 for r in requests),
                "agreed_amount": sum(r.agreed_amount or 0 for r in requests),
            }

            project.conversation_stats = {
                "total": len(conversation_counts),
                "active": len([c for c in conversation_counts if c.status == "active"]),
                "negotiating": len([c for c in conversation_counts if c.status == "negotiating"]),
                "agreed": len([c for c in conversation_counts if c.status == "agreed"]),
            }

            # Get last activity timestamp
            activity_dates = [project.updated_at or project.created_at]
            activity_dates.extend(r.updated_at or r.created_at for r in requests)
            activity_dates.extend(c.updated_at or c.created_at for c in conversation_counts)
            project.last_activity = max(d for d in activity_dates if d is not None)

        return projects
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch projects: {str(e)}",
        )


def get_project(db: Session, project_id: int) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {project_id} not found"
        )
    return project


def get_project_by_id_and_user(db: Session, project_id: int, user_id: int) -> models.Project:
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == user_id)
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found or you don't have access",
        )
    return project


def update_project(
    db: Session, project_id: int, project_update: schemas.ProjectUpdate, user_id: int
) -> models.Project:
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
            detail=f"Failed to update project: {str(e)}",
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
            detail=f"Failed to delete project: {str(e)}",
        )


# Refactored function to use "General Requests" project
def get_or_create_general_requests_project(user_id: int, db: Session):
    project = (
        db.query(models.Project)
        .filter(models.Project.user_id == user_id, models.Project.name == "General Requests")
        .first()
    )
    if not project:
        # Create the "General Requests" project if it doesn't exist
        new_project = models.Project(
            name="General Requests",
            description="Default project for unassigned requests",
            user_id=user_id,
        )
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
                detail="Cannot delete project that contains requests. Please delete all requests first.",
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
            detail=f"Failed to delete project: {str(e)}",
        )


def get_project(db: Session, project_id: int) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Project with id {project_id} not found"
        )
    return project


def get_project_stats(db: Session, project_id: int):
    """Get statistics about requests in a project."""
    return {
        "total_requests": db.query(models.Request)
        .filter(models.Request.project_id == project_id)
        .count(),
        "open_requests": db.query(models.Request)
        .filter(models.Request.project_id == project_id)
        .filter(models.Request.status == "open")
        .count(),
        "completed_requests": db.query(models.Request)
        .filter(models.Request.project_id == project_id)
        .filter(models.Request.status == "completed")
        .count(),
    }
