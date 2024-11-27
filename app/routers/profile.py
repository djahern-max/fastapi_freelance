from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas, database, oauth2

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me", response_model=schemas.UserOut)
def get_profile(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get current user's profile"""
    if current_user.user_type == models.UserType.developer:
        current_user.developer_profile = (
            db.query(models.DeveloperProfile)
            .filter(models.DeveloperProfile.user_id == current_user.id)
            .first()
        )
    elif current_user.user_type == models.UserType.client:
        current_user.client_profile = (
            db.query(models.ClientProfile)
            .filter(models.ClientProfile.user_id == current_user.id)
            .first()
        )
    return current_user


@router.get("/developer", response_model=schemas.DeveloperProfileOut)
def get_developer_profile(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get developer profile"""
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only developers can access developer profiles",
        )

    profile = (
        db.query(models.DeveloperProfile)
        .filter(models.DeveloperProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return profile


@router.get("/client", response_model=schemas.ClientProfileOut)
def get_client_profile(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get client profile"""
    if current_user.user_type != models.UserType.client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can access client profiles",
        )

    profile = (
        db.query(models.ClientProfile)
        .filter(models.ClientProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return profile


@router.post(
    "/developer", response_model=schemas.DeveloperProfileOut, status_code=status.HTTP_201_CREATED
)
def create_developer_profile(
    profile_data: schemas.DeveloperProfileCreate,
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Create a new developer profile"""
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only developers can create developer profiles",
        )

    existing_profile = (
        db.query(models.DeveloperProfile)
        .filter(models.DeveloperProfile.user_id == current_user.id)
        .first()
    )
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Profile already exists"
        )

    # Initialize with default values for new fields
    profile_data_dict = profile_data.model_dump()
    profile_data_dict.update(
        {"user_id": current_user.id, "rating": None, "total_projects": 0, "success_rate": 0.0}
    )

    profile = models.DeveloperProfile(**profile_data_dict)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.post(
    "/client", response_model=schemas.ClientProfileOut, status_code=status.HTTP_201_CREATED
)
def create_client_profile(
    profile_data: schemas.ClientProfileCreate,
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Create a new client profile"""
    if current_user.user_type != models.UserType.client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can create client profiles",
        )

    # Check if a profile already exists
    existing_profile = (
        db.query(models.ClientProfile)
        .filter(models.ClientProfile.user_id == current_user.id)
        .first()
    )
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Profile already exists"
        )

    profile = models.ClientProfile(user_id=current_user.id, **profile_data.dict())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/developer", response_model=schemas.DeveloperProfileOut)
def update_developer_profile(
    profile_update: schemas.DeveloperProfileUpdate,
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Update developer profile"""
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only developers can update developer profiles",
        )

    profile = (
        db.query(models.DeveloperProfile)
        .filter(models.DeveloperProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    update_data = profile_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile


@router.put("/client", response_model=schemas.ClientProfileOut)
def update_client_profile(
    profile_update: schemas.ClientProfileUpdate,
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Update client profile"""
    if current_user.user_type != models.UserType.client:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only clients can update client profiles"
        )

    profile = (
        db.query(models.ClientProfile)
        .filter(models.ClientProfile.user_id == current_user.id)
        .first()
    )

    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    for key, value in profile_update.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)
    return profile
