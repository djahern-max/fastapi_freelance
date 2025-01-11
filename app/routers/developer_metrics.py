# app/routers/developer_metrics.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Union

from ..database import get_db
from ..models import User, DeveloperRating, Video, Showcase, DeveloperProfile
from ..schemas import DeveloperMetricsResponse

router = APIRouter(prefix="/developers", tags=["Developer Metrics"])


@router.get("/{developer_id}/metrics", response_model=DeveloperMetricsResponse)
async def get_developer_metrics(developer_id: int, db: Session = Depends(get_db)):
    # First check if developer exists
    developer = (
        db.query(User).join(DeveloperProfile).filter(User.id == developer_id).first()
    )

    if not developer:
        raise HTTPException(status_code=404, detail="Developer not found")

    try:
        # Get profile rating from DeveloperRating
        profile_rating = (
            db.query(func.coalesce(func.avg(DeveloperRating.stars), 0.0))
            .join(DeveloperProfile)
            .filter(DeveloperProfile.user_id == developer_id)
            .scalar()
        )

        # Get video rating average
        video_rating = (
            db.query(func.coalesce(func.avg(Video.average_rating), 0.0))
            .filter(Video.user_id == developer_id)
            .scalar()
        )

        # Get showcase rating average
        showcase_rating = (
            db.query(func.coalesce(func.avg(Showcase.average_rating), 0.0))
            .filter(Showcase.developer_id == developer_id)
            .scalar()
        )

        # Calculate weighted composite score
        composite_score = (
            float(profile_rating) * 0.4  # 40% profile rating
            + float(video_rating) * 0.3  # 30% video rating
            + float(showcase_rating) * 0.3  # 30% showcase rating
        )

        # Get counts
        total_videos = db.query(Video).filter(Video.user_id == developer_id).count()

        total_showcases = (
            db.query(Showcase).filter(Showcase.developer_id == developer_id).count()
        )

        total_likes = (
            db.query(func.coalesce(func.sum(Video.likes), 0))
            .filter(Video.user_id == developer_id)
            .scalar()
        )

        # Get developer profile stats
        developer_profile = (
            db.query(DeveloperProfile)
            .filter(DeveloperProfile.user_id == developer_id)
            .first()
        )

        return {
            "profile_rating": float(profile_rating),
            "video_rating": float(video_rating),
            "showcase_rating": float(showcase_rating),
            "composite_score": float(composite_score),
            "total_videos": total_videos,
            "total_showcases": total_showcases,
            "total_likes": int(total_likes),
            "total_projects": (
                developer_profile.total_projects if developer_profile else 0
            ),
            "success_rate": (
                developer_profile.success_rate if developer_profile else 0.0
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="An error occurred while calculating developer metrics",
        )
