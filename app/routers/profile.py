from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas, database, oauth2

router = APIRouter(
    prefix="/profile",
    tags=["Profile"]
)

@router.get("/me", response_model=schemas.UserOut)
def get_profile(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Get current user's profile"""
    if current_user.user_type == models.UserType.DEVELOPER:
        current_user.developer_profile = db.query(models.DeveloperProfile).filter(
            models.DeveloperProfile.user_id == current_user.id
        ).first()
    elif current_user.user_type == models.UserType.CLIENT:
        current_user.client_profile = db.query(models.ClientProfile).filter(
            models.ClientProfile.user_id == current_user.id
        ).first()
    return current_user

@router.put("/developer", response_model=schemas.DeveloperProfileOut)
def update_developer_profile(
    profile_update: schemas.DeveloperProfileUpdate,
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Update developer profile"""
    if current_user.user_type != models.UserType.DEVELOPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only developers can update developer profiles"
        )

    profile = db.query(models.DeveloperProfile).filter(
        models.DeveloperProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    for key, value in profile_update.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile

@router.put("/client", response_model=schemas.ClientProfileOut)
def update_client_profile(
    profile_update: schemas.ClientProfileUpdate,
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db)
):
    """Update client profile"""
    if current_user.user_type != models.UserType.CLIENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can update client profiles"
        )

    profile = db.query(models.ClientProfile).filter(
        models.ClientProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    for key, value in profile_update.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile