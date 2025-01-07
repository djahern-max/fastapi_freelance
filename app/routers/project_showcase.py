from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from typing import Optional, List
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
import logging
import os
import uuid
import boto3
import httpx
from ..models import User
from .. import schemas, models
from ..database import get_db
from ..oauth2 import get_current_user
from ..models import Showcase, ShowcaseRating
from ..crud.project_showcase import (
    create_project_showcase,
    get_project_showcase,
    get_developer_showcases,
    update_project_showcase,
    delete_project_showcase,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/project-showcase", tags=["project-showcase"])

s3 = boto3.client(
    "s3",
    region_name=os.getenv("SPACES_REGION"),
    endpoint_url=os.getenv("SPACES_ENDPOINT"),
    aws_access_key_id=os.getenv("SPACES_KEY"),
    aws_secret_access_key=os.getenv("SPACES_SECRET"),
)


@router.post("/", response_model=schemas.ProjectShowcase)
async def create_showcase(
    title: str = Form(...),
    description: str = Form(...),
    project_url: Optional[str] = Form(None),
    repository_url: Optional[str] = Form(None),
    image_file: Optional[UploadFile] = File(None),
    readme_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # Initialize S3 client
        s3 = boto3.client(
            "s3",
            region_name=os.getenv("SPACES_REGION"),
            endpoint_url=f"https://{os.getenv('SPACES_REGION')}.digitaloceanspaces.com",
            aws_access_key_id=os.getenv("SPACES_KEY"),
            aws_secret_access_key=os.getenv("SPACES_SECRET"),
        )

        image_url = None
        if image_file:
            # Generate unique filename with UUID
            file_extension = os.path.splitext(image_file.filename)[1]
            image_key = f"showcase-images/{uuid.uuid4()}{file_extension}"

            # Upload to Spaces
            await image_file.seek(0)
            image_content = await image_file.read()

            s3.put_object(
                Bucket=os.getenv("SPACES_BUCKET"),
                Key=image_key,
                Body=image_content,
                ACL="public-read",
                ContentType=image_file.content_type,
            )

            # Construct the full URL
            image_url = f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{image_key}"

        # Handle README file similarly
        readme_url = None
        if readme_file:
            if not readme_file.filename.endswith(".md"):
                raise HTTPException(
                    status_code=400, detail="README must be a markdown file"
                )

            readme_key = f"showcase-readmes/{uuid.uuid4()}.md"

            await readme_file.seek(0)
            readme_content = await readme_file.read()

            s3.put_object(
                Bucket=os.getenv("SPACES_BUCKET"),
                Key=readme_key,
                Body=readme_content,
                ACL="public-read",
                ContentType="text/markdown",
            )

            readme_url = f"https://{os.getenv('SPACES_BUCKET')}.{os.getenv('SPACES_REGION')}.digitaloceanspaces.com/{readme_key}"

        # Create showcase in database
        showcase_data = {
            "title": title,
            "description": description,
            "project_url": project_url,
            "repository_url": repository_url,
            "image_url": image_url,
            "readme_url": readme_url,
            "developer_id": current_user.id,
        }

        db_showcase = models.Showcase(**showcase_data)
        db.add(db_showcase)
        db.commit()
        db.refresh(db_showcase)

        return db_showcase

    except Exception as e:
        logger.error(f"Error creating showcase: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{showcase_id}", response_model=schemas.ProjectShowcase)
def read_showcase(showcase_id: int, db: Session = Depends(get_db)):
    db_showcase = get_project_showcase(db, showcase_id)
    if not db_showcase:
        raise HTTPException(status_code=404, detail="Project showcase not found")
    return db_showcase


@router.get("/developer/{developer_id}", response_model=List[schemas.ProjectShowcase])
async def get_developer_showcases_route(
    developer_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    try:
        showcases = await get_developer_showcases_crud(db, developer_id, skip, limit)
        return showcases or []
    except Exception as e:
        logger.error(f"Error fetching developer showcases: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Rename the crud function to avoid naming conflict
async def get_developer_showcases_crud(
    db: Session, developer_id: int, skip: int = 0, limit: int = 100
):
    return (
        db.query(Showcase)
        .filter(Showcase.developer_id == developer_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


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


@router.get("/{showcase_id}/readme")  # Remove duplicate project-showcase
async def get_showcase_readme(showcase_id: int, db: Session = Depends(get_db)):
    showcase = get_project_showcase(db, showcase_id)
    if not showcase:
        raise HTTPException(status_code=404, detail="Showcase not found")

    if not showcase.readme_url:
        raise HTTPException(status_code=404, detail="No README found")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(showcase.readme_url)
            return {"content": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{showcase_id}/rating", response_model=schemas.ShowcaseRatingResponse)
async def rate_showcase(
    showcase_id: int,
    rating: schemas.ShowcaseRatingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    showcase = (
        db.query(models.Showcase).filter(models.Showcase.id == showcase_id).first()
    )
    if not showcase:
        raise HTTPException(status_code=404, detail="Showcase not found")

    if showcase.developer_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot rate your own showcase")

    try:
        # Check for existing rating
        existing_rating = (
            db.query(models.ShowcaseRating)
            .filter(
                models.ShowcaseRating.showcase_id == showcase_id,
                models.ShowcaseRating.rater_id == current_user.id,
            )
            .first()
        )

        if existing_rating:
            existing_rating.stars = rating.stars
            db.commit()
        else:
            new_rating = models.ShowcaseRating(
                showcase_id=showcase_id, rater_id=current_user.id, stars=rating.stars
            )
            db.add(new_rating)
            db.commit()

        # Update showcase stats
        stats = (
            db.query(
                func.avg(models.ShowcaseRating.stars).label("average"),
                func.count(models.ShowcaseRating.id).label("total"),
            )
            .filter(models.ShowcaseRating.showcase_id == showcase_id)
            .first()
        )

        showcase.average_rating = float(stats[0]) if stats[0] else 0.0
        showcase.total_ratings = stats[1] or 0
        db.commit()

        return {
            "success": True,
            "average_rating": showcase.average_rating,
            "total_ratings": showcase.total_ratings,
            "message": "Rating submitted successfully",
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{showcase_id}/rating", response_model=schemas.ShowcaseRatingStats)
async def get_showcase_rating(showcase_id: int, db: Session = Depends(get_db)):
    # Calculate average rating and total ratings directly from ShowcaseRating table
    rating_stats = (
        db.query(
            func.avg(models.ShowcaseRating.stars).label("average_rating"),
            func.count(models.ShowcaseRating.id).label("total_ratings"),
        )
        .filter(models.ShowcaseRating.showcase_id == showcase_id)
        .first()
    )

    return {
        "average_rating": float(rating_stats[0]) if rating_stats[0] else 0.0,
        "total_ratings": rating_stats[1] if rating_stats[1] else 0,
    }


@router.get("/{showcase_id}/user-rating", response_model=schemas.ShowcaseRating)
async def get_user_showcase_rating(
    showcase_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rating = (
        db.query(models.ShowcaseRating)
        .filter(
            models.ShowcaseRating.showcase_id == showcase_id,
            models.ShowcaseRating.rater_id == current_user.id,
        )
        .first()
    )

    if not rating:
        raise HTTPException(status_code=404, detail="No rating found for this user")

    return rating


async def update_showcase_stats(db: Session, showcase_id: int):
    """Helper function to update showcase rating statistics"""
    stats = (
        db.query(
            func.avg(models.ShowcaseRating.stars).label(
                "average_rating"
            ),  # Changed from rating to stars
            func.count(models.ShowcaseRating.id).label("total_ratings"),
        )
        .filter(models.ShowcaseRating.showcase_id == showcase_id)
        .first()
    )

    showcase = get_project_showcase(db, showcase_id)
    if showcase:
        showcase.average_rating = float(stats[0]) if stats[0] else 0.0
        showcase.total_ratings = stats[1]
        db.commit()


@router.get("/", response_model=List[schemas.ProjectShowcase])
async def list_showcases(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """Get all project showcases"""
    try:
        showcases = (
            db.query(models.Showcase)
            .order_by(models.Showcase.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return showcases
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/{showcase_id}/share")
async def create_share_link(
    showcase_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    showcase = (
        db.query(models.Showcase).filter(models.Showcase.id == showcase_id).first()
    )
    if not showcase:
        raise HTTPException(status_code=404, detail="Showcase not found")

    share_token = str(uuid.uuid4())
    showcase.share_token = share_token
    db.commit()

    return {"share_token": share_token}
