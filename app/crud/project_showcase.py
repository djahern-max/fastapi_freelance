from sqlalchemy.orm import Session
from .. import models, schemas
from fastapi import HTTPException, status


def create_project_showcase(
    db: Session, showcase: schemas.ProjectShowcaseCreate, developer_id: int
):
    db_showcase = models.ProjectShowcase(**showcase.dict(), developer_id=developer_id)
    db.add(db_showcase)
    db.commit()
    db.refresh(db_showcase)
    return db_showcase


def get_project_showcase(db: Session, showcase_id: int):
    return (
        db.query(models.ProjectShowcase)
        .filter(models.ProjectShowcase.id == showcase_id)
        .first()
    )


def get_developer_showcases(
    db: Session, developer_id: int, skip: int = 0, limit: int = 100
):
    return (
        db.query(models.ProjectShowcase)
        .filter(models.ProjectShowcase.developer_id == developer_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_project_showcase(
    db: Session,
    showcase_id: int,
    showcase: schemas.ProjectShowcaseCreate,
    developer_id: int,
):
    db_showcase = get_project_showcase(db, showcase_id)
    if not db_showcase:
        raise HTTPException(status_code=404, detail="Project showcase not found")
    if db_showcase.developer_id != developer_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this showcase"
        )

    for key, value in showcase.dict().items():
        setattr(db_showcase, key, value)

    db.commit()
    db.refresh(db_showcase)
    return db_showcase


def delete_project_showcase(db: Session, showcase_id: int, developer_id: int):
    db_showcase = get_project_showcase(db, showcase_id)
    if not db_showcase:
        raise HTTPException(status_code=404, detail="Project showcase not found")
    if db_showcase.developer_id != developer_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this showcase"
        )

    db.delete(db_showcase)
    db.commit()
    return {"message": "Project showcase deleted successfully"}
