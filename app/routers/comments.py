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
    comment: schemas.RequestCommentCreate,  # Updated to RequestCommentCreate
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    # Ensure the post exists (assuming you have a `post_id` to associate the comment)
    post_id = comment.post_id
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    new_comment = models.Comment(
        content=comment.content,  # Corrected the parameter to 'content'
        user_id=current_user.id,
        post_id=post_id
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment
