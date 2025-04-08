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
    limit: int = Query(100, ge=1, le=500),
    skills: Optional[str] = None,
    min_experience: Optional[int] = None,
    db: Session = Depends(database.get_db),
):
    """Get list of public developer profiles with optional filtering"""
    query = db.query(models.DeveloperProfile).filter(
        models.DeveloperProfile.is_public == True
    )

    if skills:
        query = query.filter(models.DeveloperProfile.skills.ilike(f"%{skills}%"))

    if min_experience is not None:
        query = query.filter(models.DeveloperProfile.experience_years >= min_experience)

    # Order by rating and success factor (rate)
    query = query.order_by(
        desc(models.DeveloperProfile.rating), desc(models.DeveloperProfile.success_rate)
    )

    return query.offset(skip).limit(limit).all()


@router.get(
    "/developers/{user_id}/public", response_model=schemas.DeveloperProfilePublic
)
def get_public_developer_profile(user_id: int, db: Session = Depends(database.get_db)):
    """Get a specific public developer profile"""
    profile = (
        db.query(models.DeveloperProfile)
        .filter(
            models.DeveloperProfile.user_id == user_id,
            models.DeveloperProfile.is_public == True,
        )
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Public profile not found"
        )

    return profile


@router.patch("/{id}", response_model=schemas.ConversationOut)
def update_conversation_status(
    id: int,
    status: schemas.ConversationStatus,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    conversation = (
        db.query(models.Conversation).filter(models.Conversation.id == id).first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if user is part of the conversation
    if current_user.id not in [
        conversation.starter_user_id,
        conversation.recipient_user_id,
    ]:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this conversation"
        )

    conversation.status = status
    db.commit()
    db.refresh(conversation)

    return conversation
