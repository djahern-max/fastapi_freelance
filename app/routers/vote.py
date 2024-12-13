from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .. import schemas, models, database, oauth2


router = APIRouter(
    tags=["Votes"],
)


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from .. import schemas, models, database, oauth2

router = APIRouter(tags=["Votes"])


@router.post("/vote", status_code=status.HTTP_201_CREATED)
def vote(
    vote: schemas.Vote,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    # Check if video exists
    video = db.query(models.Video).filter(models.Video.id == vote.video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video with id {vote.video_id} does not exist",
        )

    vote_query = db.query(models.Vote).filter(
        models.Vote.video_id == vote.video_id, models.Vote.user_id == current_user.id
    )
    found_vote = vote_query.first()

    try:
        if vote.dir == 1:
            if found_vote:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Already voted on this video"
                )
            new_vote = models.Vote(video_id=vote.video_id, user_id=current_user.id)
            db.add(new_vote)
            db.commit()
            return {"message": "Successfully liked the video"}
        else:
            if not found_vote:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Vote does not exist"
                )
            vote_query.delete(synchronize_session=False)
            db.commit()
            return {"message": "Successfully unliked the video"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}"
        )
