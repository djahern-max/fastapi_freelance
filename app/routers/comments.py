from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.oauth2 import get_current_user

router = APIRouter(
    prefix="/comments",
    tags=["Comments"]
)

@router.post("/", response_model=schemas.RequestCommentResponse)
def create_comment(
    comment: schemas.RequestCommentCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Validate that the associated request exists
    request_id = comment.request_id
    request = db.query(models.Request).filter(models.Request.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    new_comment = models.RequestComment(
        content=comment.content,
        user_id=current_user.id,
        request_id=request_id,
        parent_id=comment.parent_id
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment