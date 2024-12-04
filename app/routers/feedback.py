from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, oauth2
from ..database import get_db

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("/", response_model=schemas.FeedbackResponse)
def create_feedback(feedback: schemas.FeedbackCreate, db: Session = Depends(get_db)):
    # Create feedback without user_id since we removed it from the model
    new_feedback = models.Feedback(**feedback.dict())  # Remove user_id=None
    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)
    return new_feedback


@router.get("/", response_model=List[schemas.FeedbackResponse])
def get_feedback(
    db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)
):
    # Only allow admin users to view all feedback
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view feedback")

    feedback = db.query(models.Feedback).all()
    return feedback
