from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.oauth2 import get_current_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.oauth2 import get_current_user
from sqlalchemy import or_

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
    request = db.query(models.Request).filter(models.Request.id == comment.request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # If it's a private request, verify the user has access
    if not request.is_public:
        if current_user.user_type == models.UserType.DEVELOPER:
            # Developers can only comment if they have an active conversation
            conversation = db.query(models.Conversation).filter(
                models.Conversation.request_id == request.id,
                or_(
                    models.Conversation.starter_user_id == current_user.id,
                    models.Conversation.recipient_user_id == current_user.id
                )
            ).first()
            
            if not conversation:
                raise HTTPException(
                    status_code=403,
                    detail="Must start a conversation before commenting"
                )
        elif current_user.id != request.user_id:
            # Clients can only comment on their own requests
            raise HTTPException(
                status_code=403,
                detail="Not authorized to comment on this request"
            )

    new_comment = models.RequestComment(
        content=comment.content,
        user_id=current_user.id,
        request_id=comment.request_id,
        parent_id=comment.parent_id
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment