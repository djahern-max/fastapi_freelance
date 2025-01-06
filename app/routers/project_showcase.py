from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from typing import Optional
from sqlalchemy.orm import Session
from typing import List
import json
from .. import schemas, models
from ..database import get_db
from ..oauth2 import get_current_user
from ..crud.project_showcase import (
    create_project_showcase,
    get_project_showcase,
    get_developer_showcases,
    update_project_showcase,
    delete_project_showcase,
)

router = APIRouter(prefix="/project-showcase", tags=["project-showcase"])


@router.post("/", response_model=schemas.ProjectShowcase)
async def create_showcase(
    title: str = Form(...),
    description: str = Form(...),
    project_url: Optional[str] = Form(None),
    repository_url: Optional[str] = Form(None),
    demo_url: Optional[str] = Form(None),
    readme_file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        # Create showcase data without video_ids
        showcase_data = schemas.ProjectShowcaseCreate(
            title=title,
            description=description,
            project_url=project_url,
            repository_url=repository_url,
            demo_url=demo_url,
        )

        return await create_project_showcase(
            db=db,
            showcase=showcase_data,
            developer_id=current_user.id,
            image_file=image_file,
            readme_file=readme_file,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{showcase_id}", response_model=schemas.ProjectShowcase)
def read_showcase(showcase_id: int, db: Session = Depends(get_db)):
    db_showcase = get_project_showcase(db, showcase_id)
    if not db_showcase:
        raise HTTPException(status_code=404, detail="Project showcase not found")
    return db_showcase


@router.get("/developer/{developer_id}", response_model=List[schemas.ProjectShowcase])
def read_developer_showcases(
    developer_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    return get_developer_showcases(db, developer_id, skip, limit)


@router.put("/{showcase_id}", response_model=schemas.ProjectShowcase)
def update_showcase(
    showcase_id: int,
    showcase: schemas.ProjectShowcaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return update_project_showcase(db, showcase_id, showcase, current_user.id)


@router.delete("/{showcase_id}")
def delete_showcase(
    showcase_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return delete_project_showcase(db, showcase_id, current_user.id)
