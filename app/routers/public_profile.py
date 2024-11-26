from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from .. import models, schemas, database, oauth2
from typing import Optional
from fastapi import Body

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/developers/public", response_model=List[schemas.DeveloperProfilePublic])
def get_public_developers(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    skills: Optional[str] = None,
    min_experience: Optional[int] = None,
    db: Session = Depends(database.get_db),
):
    """Get list of public developer profiles with optional filtering"""
    query = db.query(models.DeveloperProfile).filter(models.DeveloperProfile.is_public == True)

    if skills:
        query = query.filter(models.DeveloperProfile.skills.ilike(f"%{skills}%"))

    if min_experience is not None:
        query = query.filter(models.DeveloperProfile.experience_years >= min_experience)

    # Order by rating and success rate
    query = query.order_by(
        desc(models.DeveloperProfile.rating), desc(models.DeveloperProfile.success_rate)
    )

    return query.offset(skip).limit(limit).all()


@router.get("/developers/{user_id}/public", response_model=schemas.DeveloperProfilePublic)
def get_public_developer_profile(user_id: int, db: Session = Depends(database.get_db)):
    """Get a specific public developer profile"""
    profile = (
        db.query(models.DeveloperProfile)
        .filter(
            models.DeveloperProfile.user_id == user_id, models.DeveloperProfile.is_public == True
        )
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Public profile not found"
        )

    return profile


@router.patch("/developer/visibility", response_model=schemas.DeveloperProfilePublic)
def update_profile_visibility(
    make_public: bool = Body(..., embed=True),  # Changed this line
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Update the public visibility of a developer profile"""
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only developers can update profile visibility",
        )

    profile = (
        db.query(models.DeveloperProfile)
        .filter(models.DeveloperProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    profile.is_public = make_public
    db.commit()
    db.refresh(profile)
    return profile
