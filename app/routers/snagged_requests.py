# app/routers/snagged_requests.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from .. import models, schemas, database, oauth2
from ..middleware import require_active_subscription
from ..schemas import SnaggedRequestWithDetails
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/snagged-requests", tags=["Snagged Requests"])


@router.get("/", response_model=List[SnaggedRequestWithDetails])
def get_snagged_requests(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(status_code=403, detail="Only developers can view snagged requests")

    # Get snagged requests with full request and user information
    snagged_requests = (
        db.query(models.SnaggedRequest)
        .join(models.Request, models.SnaggedRequest.request_id == models.Request.id)
        .join(models.User, models.Request.user_id == models.User.id)
        .filter(
            models.SnaggedRequest.developer_id == current_user.id,
            models.SnaggedRequest.is_active == True,
        )
        .with_entities(
            models.SnaggedRequest, models.Request, models.User.username.label("owner_username")
        )
        .all()
    )

    # Format the response
    result = []
    for snagged, request, owner_username in snagged_requests:
        result.append(
            {
                "id": snagged.id,
                "request_id": snagged.request_id,
                "developer_id": snagged.developer_id,
                "snagged_at": snagged.snagged_at,
                "is_active": snagged.is_active,
                "request": {
                    "id": request.id,
                    "title": request.title,
                    "content": request.content,
                    "status": request.status,
                    "estimated_budget": request.estimated_budget,
                    "owner_username": owner_username,
                },
            }
        )

    return result


@router.get("/", response_model=List[schemas.SnaggedRequestOut])
def get_snagged_requests(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(status_code=403, detail="Only developers can view snagged requests")

    snagged_requests = (
        db.query(models.SnaggedRequest)
        .filter(
            models.SnaggedRequest.developer_id == current_user.id,
            models.SnaggedRequest.is_active == True,
        )
        .all()
    )

    return snagged_requests


@router.delete("/{request_id}", status_code=status.HTTP_200_OK)
def remove_snagged_request(
    request_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    snagged_request = (
        db.query(models.SnaggedRequest)
        .filter(
            models.SnaggedRequest.request_id == request_id,
            models.SnaggedRequest.developer_id == current_user.id,
        )
        .first()
    )

    if not snagged_request:
        raise HTTPException(status_code=404, detail="Snagged request not found")

    snagged_request.is_active = False
    db.commit()
    return {"message": "Request removed from snagged list"}


@router.post("/", response_model=schemas.SnaggedRequestWithDetails)
def create_snagged_request(
    snag: schemas.SnaggedRequestCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        if current_user.user_type != models.UserType.developer:
            raise HTTPException(status_code=403, detail="Only developers can snag requests")

        # Get the request
        request = db.query(models.Request).filter(models.Request.id == snag.request_id).first()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # Check if already snagged
        existing_snag = (
            db.query(models.SnaggedRequest)
            .filter(
                models.SnaggedRequest.request_id == snag.request_id,
                models.SnaggedRequest.developer_id == current_user.id,
                models.SnaggedRequest.is_active == True,
            )
            .first()
        )

        if existing_snag:
            raise HTTPException(status_code=400, detail="Request already snagged")

        # Create snag and conversation
        new_snag = models.SnaggedRequest(request_id=snag.request_id, developer_id=current_user.id)
        db.add(new_snag)
        db.flush()

        conversation = models.Conversation(
            request_id=snag.request_id,
            starter_user_id=current_user.id,
            recipient_user_id=request.user_id,
            status=models.ConversationStatus.active,
        )
        db.add(conversation)
        db.flush()

        message = models.ConversationMessage(
            conversation_id=conversation.id, user_id=current_user.id, content=snag.message
        )
        db.add(message)
        db.flush()

        # Quietly attempt to add profile link if requested
        if snag.profile_link:
            try:
                profile_link = models.ConversationContentLink(
                    conversation_id=conversation.id,
                    message_id=message.id,
                    content_type="profile",
                    content_id=current_user.id,
                )
                db.add(profile_link)
            except:
                pass  # Silently continue if profile link fails

        # Quietly attempt to add any existing video links
        if snag.video_ids:
            try:
                existing_videos = (
                    db.query(models.Video)
                    .filter(
                        models.Video.id.in_(snag.video_ids), models.Video.user_id == current_user.id
                    )
                    .all()
                )

                for video in existing_videos:
                    video_link = models.ConversationContentLink(
                        conversation_id=conversation.id,
                        message_id=message.id,
                        content_type="video",
                        content_id=video.id,
                    )
                    db.add(video_link)
            except:
                pass  # Silently continue if video links fail

        db.commit()

        result = (
            db.query(models.SnaggedRequest)
            .join(models.Request)
            .join(models.User, models.Request.user_id == models.User.id)
            .filter(models.SnaggedRequest.id == new_snag.id)
            .with_entities(
                models.SnaggedRequest, models.Request, models.User.username.label("owner_username")
            )
            .first()
        )

        snagged, request, owner_username = result

        return {
            "id": snagged.id,
            "request_id": snagged.request_id,
            "developer_id": snagged.developer_id,
            "snagged_at": snagged.snagged_at,
            "is_active": snagged.is_active,
            "request": {
                "id": request.id,
                "title": request.title,
                "content": request.content,
                "status": request.status,
                "estimated_budget": request.estimated_budget,
                "owner_username": owner_username,
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
