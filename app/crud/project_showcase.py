import boto3
import os
import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from fastapi import UploadFile
from .. import models, schemas
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Create a thread pool executor for running boto3 operations
executor = ThreadPoolExecutor(max_workers=4)

s3 = boto3.client(
    "s3",
    region_name=os.getenv("SPACES_REGION"),
    endpoint_url=os.getenv("SPACES_ENDPOINT"),
    aws_access_key_id=os.getenv("SPACES_KEY"),
    aws_secret_access_key=os.getenv("SPACES_SECRET"),
)


async def upload_to_s3(file_content: bytes, bucket: str, key: str, content_type: str):
    """Async wrapper for S3 upload"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        executor,
        lambda: s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_content,
            ACL="public-read",
            ContentType=content_type,
        ),
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
            file_content = await image_file.read()
            unique_filename = (
                f"{uuid.uuid4()}{os.path.splitext(image_file.filename)[1]}"
            )
            key = f"showcase-images/{unique_filename}"

            await upload_to_s3(
                file_content, os.getenv("SPACES_BUCKET"), key, image_file.content_type
            )

            image_url = f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{key}"

        # Handle README upload
        readme_url = None
        if readme_file:
            if not readme_file.filename.endswith(".md"):
                raise HTTPException(
                    status_code=400, detail="README must be a markdown file"
                )

            file_content = await readme_file.read()
            unique_filename = f"{uuid.uuid4()}.md"
            key = f"showcase-readmes/{unique_filename}"

            await upload_to_s3(
                file_content, os.getenv("SPACES_BUCKET"), key, "text/markdown"
            )

            readme_url = f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{key}"

        # Create showcase with exact fields from schema
        showcase_dict = showcase.model_dump()
        db_showcase = models.Showcase(
            **showcase_dict,
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

    showcase_data = showcase.dict(exclude_unset=True)
    for key, value in showcase_data.items():
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
