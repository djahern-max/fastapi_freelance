from sqlalchemy.orm import Session, selectinload, joinedload
import boto3
import os
import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from fastapi import UploadFile
from .. import models, schemas
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

# Add logger
logger = logging.getLogger(__name__)

# Your existing executor and s3 client setup is good
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
    try:
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
        logger.info(f"Successfully uploaded file to {key}")
    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


async def validate_and_upload_file(
    file: UploadFile, folder: str, allowed_types: list = None
):
    """Helper function to validate and upload files"""
    if not file:
        return None

    try:
        # Validate file type if allowed_types provided
        if allowed_types and not any(
            file.content_type.startswith(t) for t in allowed_types
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
            )

        file_content = await file.read()
        unique_filename = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
        key = f"{folder}/{unique_filename}"

        await upload_to_s3(
            file_content, os.getenv("SPACES_BUCKET"), key, file.content_type
        )

        return f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{key}"

    except Exception as e:
        logger.error(f"Error processing file upload: {str(e)}")
        raise
    finally:
        await file.seek(0)


async def create_project_showcase(
    db: Session,
    showcase: schemas.ProjectShowcaseCreate,
    developer_id: int,
    image_file: Optional[UploadFile] = None,
    readme_file: Optional[UploadFile] = None,
):
    try:
        # Handle image upload with validation
        image_url = (
            await validate_and_upload_file(
                image_file, "showcase-images", allowed_types=["image/"]
            )
            if image_file
            else None
        )

        # Handle README upload with validation
        readme_url = None
        if readme_file:
            if not readme_file.filename.endswith(".md"):
                raise HTTPException(
                    status_code=400, detail="README must be a markdown file"
                )
            readme_url = await validate_and_upload_file(readme_file, "showcase-readmes")

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

        logger.info(f"Created showcase {db_showcase.id} for developer {developer_id}")
        return db_showcase

    except Exception as e:
        logger.error(f"Error creating showcase: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def get_project_showcase(db: Session, showcase_id: int):
    """Get a single project showcase by ID"""
    return db.query(models.Showcase).filter(models.Showcase.id == showcase_id).first()


async def get_developer_showcases(
    db: Session, developer_id: int, skip: int = 0, limit: int = 100
):
    try:
        return (
            db.query(models.Showcase)
            .filter(models.Showcase.developer_id == developer_id)
            .options(
                selectinload(models.Showcase.videos),
                selectinload(models.Showcase.ratings),
                selectinload(models.Showcase.developer).load_only("id", "username"),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        raise


def update_project_showcase(
    db: Session,
    showcase_id: int,
    showcase: schemas.ProjectShowcaseCreate,
    developer_id: int,
):
    """Update a project showcase"""
    db_showcase = get_project_showcase(db, showcase_id)
    if not db_showcase:
        raise HTTPException(status_code=404, detail="Project showcase not found")
    if db_showcase.developer_id != developer_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this showcase"
        )

    for key, value in showcase.dict(exclude_unset=True).items():
        setattr(db_showcase, key, value)

    db.commit()
    db.refresh(db_showcase)
    return db_showcase


def delete_project_showcase(db: Session, showcase_id: int, developer_id: int):
    """Delete a project showcase"""
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
