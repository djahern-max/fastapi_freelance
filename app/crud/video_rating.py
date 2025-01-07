# app/crud/video_rating.py

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from typing import Optional

from ..models import Video, VideoRating
from ..schemas import DeveloperRatingCreate, VideoRatingResponse


class VideoRatingCRUD:
    def create_or_update_video_rating(
        self,
        db: Session,
        video_id: int,
        user_id: int,
        rating_data: DeveloperRatingCreate,
    ):
        # Check if rating exists
        existing_rating = (
            db.query(VideoRating)
            .filter(
                VideoRating.video_id == video_id,
                VideoRating.rater_id == user_id,
            )
            .first()
        )

        try:
            if existing_rating:
                # Update existing rating
                existing_rating.stars = rating_data.stars
                existing_rating.comment = rating_data.comment
                rating = existing_rating
            else:
                # Create new rating
                rating = VideoRating(
                    video_id=video_id,
                    rater_id=user_id,
                    stars=rating_data.stars,
                    comment=rating_data.comment,
                )
                db.add(rating)

            db.commit()
            db.refresh(rating)
            return rating

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    def get_video_rating_stats(self, db: Session, video_id: int):
        # Get average rating and total count
        stats = (
            db.query(
                func.avg(VideoRating.stars).label("average"),
                func.count(VideoRating.id).label("total"),
            )
            .filter(VideoRating.video_id == video_id)
            .first()
        )

        return {
            "average_rating": float(stats.average) if stats.average else 0.0,
            "total_ratings": stats.total,
        }

    def get_user_rating(
        self, db: Session, video_id: int, user_id: int
    ) -> Optional[VideoRating]:
        return (
            db.query(VideoRating)
            .filter(
                VideoRating.video_id == video_id,
                VideoRating.rater_id == user_id,
            )
            .first()
        )


# Create an instance to export
video_rating = VideoRatingCRUD()
