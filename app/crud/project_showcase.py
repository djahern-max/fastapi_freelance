# crud/project_showcase.py
import boto3
import os
import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from fastapi import UploadFile
from .. import models, schemas


s3 = boto3.client(
    "s3",
    region_name=os.getenv("SPACES_REGION"),
    endpoint_url=os.getenv("SPACES_ENDPOINT"),
    aws_access_key_id=os.getenv("SPACES_KEY"),
    aws_secret_access_key=os.getenv("SPACES_SECRET"),
)


async def create_project_showcase(
    db: Session,
    showcase: schemas.ProjectShowcaseCreate,
    developer_id: int,
    image_file: Optional[UploadFile] = None,
    readme_file: Optional[UploadFile] = None,
):
    try:
        # Handle image upload
        image_url = None
        if image_file:
            unique_filename = (
                f"{uuid.uuid4()}{os.path.splitext(image_file.filename)[1]}"
            )
            await s3.put_object(
                Bucket=os.getenv("SPACES_BUCKET"),
                Key=f"showcase-images/{unique_filename}",
                Body=await image_file.read(),
                ACL="public-read",
                ContentType=image_file.content_type,
            )
            image_url = f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/showcase-images/{unique_filename}"

        # Handle README upload
        readme_url = None
        if readme_file:
            if not readme_file.filename.endswith(".md"):
                raise HTTPException(
                    status_code=400, detail="README must be a markdown file"
                )

            unique_filename = f"{uuid.uuid4()}.md"
            await s3.put_object(
                Bucket=os.getenv("SPACES_BUCKET"),
                Key=f"showcase-readmes/{unique_filename}",
                Body=await readme_file.read(),
                ACL="public-read",
                ContentType="text/markdown",
            )
            readme_url = f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/showcase-readmes/{unique_filename}"

        # Create showcase
        db_showcase = models.Showcase(
            **showcase.dict(),  # Changed from showcase_data to showcase.dict()
            developer_id=developer_id,
            image_url=image_url,
            readme_url=readme_url,
        )
        db.add(db_showcase)
        db.commit()
        db.refresh(db_showcase)

        return db_showcase

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def get_project_showcase(db: Session, showcase_id: int):
    return db.query(models.Showcase).filter(models.Showcase.id == showcase_id).first()


def get_developer_showcases(
    db: Session, developer_id: int, skip: int = 0, limit: int = 100
):
    return (
        db.query(models.Showcase)
        .filter(models.Showcase.developer_id == developer_id)
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
