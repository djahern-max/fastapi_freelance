from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..oauth2 import get_current_user
from app import schemas, crud, models
from fastapi import status
from fastapi.params import Query
from typing import List

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/", response_model=schemas.ProjectOut)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        # Create the project first
        db_project = crud.crud_project.create_project(
            db=db, project=project, user_id=current_user.id
        )

        # Initialize the stats with default values
        default_stats = {
            "request_stats": {
                "total": 0,
                "open": 0,
                "completed": 0,
                "total_budget": 0.0,
                "agreed_amount": 0.0,
            },
            "conversation_stats": {
                "total": 0,
                "active": 0,
                "negotiating": 0,
                "agreed": 0,
            },
        }

        # Construct the response
        response_data = {
            "id": db_project.id,
            "name": db_project.name,
            "description": db_project.description,
            "user_id": db_project.user_id,
            "is_active": db_project.is_active,
            "created_at": db_project.created_at,
            "updated_at": db_project.updated_at,
            "request_stats": default_stats["request_stats"],
            "conversation_stats": default_stats["conversation_stats"],
            "last_activity": db_project.created_at,
        }

        return response_data

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=list[schemas.ProjectOut])
def get_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    include_stats: bool = Query(False),
):
    """Get all projects with optional stats about their requests."""
    projects = crud.crud_project.get_projects_by_user(db=db, user_id=current_user.id)
    if include_stats:
        for project in projects:
            project.stats = crud.crud_project.get_project_stats(
                db=db, project_id=project.id
            )
    return projects


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Verify user is a client before allowing deletion
    if current_user.user_type != models.UserType.client:  # Using lowercase
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can delete projects",
        )

    crud.crud_project.delete_project(
        db=db, project_id=project_id, user_id=current_user.id
    )
    return {"message": "Project deleted successfully"}


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # First get the project
    project = crud.crud_project.get_project(db=db, project_id=project_id)

    # Check if user owns the project or has access
    if project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project",
        )

    return project


@router.post("/{project_id}/publish")
def publish_project(
    project_id: int,
    project_data: schemas.ProjectPublish,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Publish a project to the public showcase"""
    project = crud.crud_project.get_project(db=db, project_id=project_id)

    if project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this project",
        )

    return crud.crud_project.publish_project(
        db=db, project_id=project_id, project_data=project_data
    )


@router.get("/showcase", response_model=List[schemas.ProjectShowcase])
def get_showcase_projects(
    skip: int = 0, limit: int = 10, db: Session = Depends(get_db)
):
    """Get all published showcase projects"""
    return crud.crud_project.get_showcase_projects(db=db, skip=skip, limit=limit)


@router.get("/showcase/{project_id}", response_model=schemas.ProjectShowcase)
def get_showcase_project(project_id: int, db: Session = Depends(get_db)):
    """Get a specific published showcase project"""
    project = crud.crud_project.get_project(db=db, project_id=project_id)

    if not project or not project.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or not public",
        )

    return project
