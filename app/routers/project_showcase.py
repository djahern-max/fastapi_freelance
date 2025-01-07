from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from typing import Optional, List
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
import logging
import os
import uuid
import boto3
import httpx
import markdown
import bleach
import json
from sqlalchemy.orm import joinedload
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
    selected_video_ids: Optional[str] = Form(None),  # Add this
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
        if selected_video_ids:
            try:
                video_ids = json.loads(selected_video_ids)
                if not isinstance(video_ids, list):
                    raise ValueError("selected_video_ids must be a JSON array")

                videos = (
                    db.query(models.Video)
                    .filter(
                        models.Video.id.in_(video_ids),
                        models.Video.user_id == current_user.id,
                    )
                    .all()
                )

                if len(videos) != len(video_ids):
                    raise HTTPException(
                        status_code=400,
                        detail="One or more video IDs are invalid or don't belong to you",
                    )

                db_showcase.videos = videos
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Invalid JSON format for selected_video_ids"
                )

        db.add(db_showcase)
        db.commit()
        db.refresh(db_showcase)

        return db_showcase

    except Exception as e:
        logger.error(f"Error creating showcase: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{showcase_id}", response_model=schemas.ProjectShowcase)
def read_showcase(showcase_id: int, db: Session = Depends(get_db)):
    db_showcase = (
        db.query(models.Showcase)
        .options(
            joinedload(models.Showcase.developer),  # Load basic user info
            joinedload(models.Showcase.developer_profile),  # Load developer profile
            joinedload(models.Showcase.videos),  # Load videos
        )
        .filter(models.Showcase.id == showcase_id)
        .first()
    )
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
async def update_showcase(
    showcase_id: int,
    showcase_data: schemas.ProjectShowcaseUpdate,  # Create this schema
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    showcase = get_project_showcase(db, showcase_id)
    if not showcase:
        raise HTTPException(status_code=404, detail="Showcase not found")

    if showcase.developer_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this showcase"
        )

    # Update the fields
    for field, value in showcase_data.dict(exclude_unset=True).items():
        setattr(showcase, field, value)

    db.commit()
    db.refresh(showcase)
    return showcase


@router.put("/{showcase_id}/files")
async def update_showcase_files(
    showcase_id: int,
    image_file: Optional[UploadFile] = File(None),
    readme_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    showcase = get_project_showcase(db, showcase_id)
    if not showcase:
        raise HTTPException(status_code=404, detail="Showcase not found")

    if showcase.developer_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this showcase"
        )

    # Handle file uploads similar to your create route
    if image_file:
        # Upload image and update image_url
        pass

    if readme_file:
        # Upload readme and update readme_url
        pass

    db.commit()
    return {"message": "Files updated successfully"}


@router.delete("/{showcase_id}")
def delete_showcase(
    showcase_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return delete_project_showcase(db, showcase_id, current_user.id)


@router.get("/{showcase_id}/readme")
async def get_showcase_readme(
    showcase_id: int, format: Optional[str] = "html", db: Session = Depends(get_db)
):
    showcase = get_project_showcase(db, showcase_id)
    if not showcase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Showcase not found"
        )

    if not showcase.readme_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No README found for this showcase",
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(showcase.readme_url)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="README file not found or inaccessible",
                )

            content = response.text

            if format == "html":
                # Convert markdown to HTML with specific extensions
                html = markdown.markdown(
                    content,
                    extensions=[
                        "fenced_code",
                        "codehilite",
                        "tables",
                        "nl2br",
                        "sane_lists",
                    ],
                )

                # Clean the HTML for security
                allowed_tags = [
                    "p",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "a",
                    "ul",
                    "ol",
                    "li",
                    "strong",
                    "em",
                    "code",
                    "pre",
                    "blockquote",
                    "table",
                    "thead",
                    "tbody",
                    "tr",
                    "th",
                    "td",
                    "br",
                    "hr",
                    "div",
                    "span",
                ]
                allowed_attrs = {
                    "a": ["href", "title"],
                    "code": ["class"],
                    "pre": ["class"],
                    "div": ["class"],
                    "span": ["class"],
                    "*": ["id"],
                }

                cleaned_html = bleach.clean(
                    html, tags=allowed_tags, attributes=allowed_attrs, strip=True
                )

                return {"content": cleaned_html, "format": "html"}
            else:
                return {"content": content, "format": "raw"}

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching README: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing README: {str(e)}",
        )


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

    # Instead of creating a new token, we'll just return the showcase ID
    # since we already have a public endpoint to view showcases
    return {"share_url": f"/showcase/{showcase_id}"}


@router.put("/{showcase_id}/videos")
async def update_showcase_videos(
    showcase_id: int,
    video_ids: List[int],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    showcase = get_project_showcase(db, showcase_id)
    if not showcase:
        raise HTTPException(status_code=404, detail="Showcase not found")

    if showcase.developer_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this showcase"
        )

    # Get all videos that belong to the user
    videos = (
        db.query(models.Video)
        .filter(models.Video.id.in_(video_ids), models.Video.user_id == current_user.id)
        .all()
    )

    if len(videos) != len(video_ids):
        raise HTTPException(
            status_code=400,
            detail="One or more video IDs are invalid or don't belong to you",
        )

    # Update the showcase's videos
    showcase.videos = videos
    db.commit()
    db.refresh(showcase)

    return {"message": "Videos updated successfully"}
