from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from typing import Optional

from ..models import (
    DeveloperProfile,
    DeveloperRating,
    Showcase,
    ShowcaseRating,  # Add these
)
from ..schemas import DeveloperRatingCreate, DeveloperRatingOut, DeveloperRatingStats


class RatingCRUD:
    def create_or_update_rating(
        self,
        db: Session,
        developer_id: int,
        user_id: int,
        rating_data: DeveloperRatingCreate,
    ) -> DeveloperRatingOut:
        # Verify the developer exists
        developer = (
            db.query(DeveloperProfile)
            .filter(DeveloperProfile.id == developer_id)
            .first()
        )
        if not developer:
            raise HTTPException(status_code=404, detail="Developer not found")

        # Check if rating already exists
        existing_rating = (
            db.query(DeveloperRating)
            .filter(
                DeveloperRating.developer_id == developer_id,
                DeveloperRating.user_id == user_id,
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
                rating = DeveloperRating(
                    developer_id=developer_id,
                    user_id=user_id,
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

    def get_developer_rating_stats(
        self, db: Session, developer_id: int
    ) -> DeveloperRatingStats:
        developer = (
            db.query(DeveloperProfile)
            .filter(DeveloperProfile.id == developer_id)
            .first()
        )
        if not developer:
            raise HTTPException(status_code=404, detail="Developer not found")

        # Get rating statistics
        stats = (
            db.query(
                func.avg(DeveloperRating.stars).label("average"),
                func.count(DeveloperRating.id).label("total"),
            )
            .filter(DeveloperRating.developer_id == developer_id)
            .first()
        )

        # Get rating distribution
        distribution = dict.fromkeys(range(1, 6), 0)
        ratings = (
            db.query(DeveloperRating.stars, func.count(DeveloperRating.id))
            .filter(DeveloperRating.developer_id == developer_id)
            .group_by(DeveloperRating.stars)
            .all()
        )

        for rating, count in ratings:
            distribution[rating] = count

        return DeveloperRatingStats(
            average_rating=float(stats.average) if stats.average else 0.0,
            total_ratings=stats.total,
            rating_distribution=distribution,
        )

    def get_user_rating(
        self, db: Session, developer_id: int, user_id: int
    ) -> Optional[DeveloperRatingOut]:
        rating = (
            db.query(DeveloperRating)
            .filter(
                DeveloperRating.developer_id == developer_id,
                DeveloperRating.user_id == user_id,
            )
            .first()
        )
        return rating


# Create an instance of the class to export
rating = RatingCRUD()

# Export the instance
__all__ = ["rating"]


class RatingCRUD:
    # ... existing methods ...

    def create_or_update_showcase_rating(
        self,
        db: Session,
        showcase_id: int,
        user_id: int,
        rating_data: DeveloperRatingCreate,
    ):
        # Verify the showcase exists
        showcase = db.query(Showcase).filter(Showcase.id == showcase_id).first()
        if not showcase:
            raise HTTPException(status_code=404, detail="Showcase not found")

        # Check if rating already exists
        existing_rating = (
            db.query(ShowcaseRating)
            .filter(
                ShowcaseRating.showcase_id == showcase_id,
                ShowcaseRating.rater_id == user_id,
            )
            .first()
        )

        try:
            if existing_rating:
                existing_rating.rating = rating_data.stars
                existing_rating.comment = rating_data.comment
                rating = existing_rating
            else:
                rating = ShowcaseRating(
                    showcase_id=showcase_id,
                    rater_id=user_id,
                    rating=rating_data.stars,
                    comment=rating_data.comment,
                )
                db.add(rating)

            db.commit()
            db.refresh(rating)
            return rating

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    def get_showcase_rating_stats(
        self, db: Session, showcase_id: int
    ) -> DeveloperRatingStats:
        # Verify the showcase exists
        showcase = db.query(Showcase).filter(Showcase.id == showcase_id).first()
        if not showcase:
            raise HTTPException(status_code=404, detail="Showcase not found")

        # Get rating statistics
        stats = (
            db.query(
                func.avg(ShowcaseRating.rating).label("average"),
                func.count(ShowcaseRating.id).label("total"),
            )
            .filter(ShowcaseRating.showcase_id == showcase_id)
            .first()
        )

        # Get rating distribution
        distribution = dict.fromkeys(range(1, 6), 0)
        ratings = (
            db.query(ShowcaseRating.rating, func.count(ShowcaseRating.id))
            .filter(ShowcaseRating.showcase_id == showcase_id)
            .group_by(ShowcaseRating.rating)
            .all()
        )

        for rating, count in ratings:
            distribution[rating] = count

        return DeveloperRatingStats(
            average_rating=float(stats.average) if stats.average else 0.0,
            total_ratings=stats.total,
            rating_distribution=distribution,
        )

    def get_showcase_user_rating(
        self, db: Session, showcase_id: int, user_id: int
    ) -> Optional[DeveloperRatingOut]:
        return (
            db.query(ShowcaseRating)
            .filter(
                ShowcaseRating.showcase_id == showcase_id,
                ShowcaseRating.rater_id == user_id,
            )
            .first()
        )
