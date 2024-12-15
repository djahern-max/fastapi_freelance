# app/routers/conversations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database, oauth2
from sqlalchemy import or_
from ..middleware import require_active_subscription


router = APIRouter(prefix="/conversations", tags=["Conversations"])


# In routers/conversations.py


@router.post("/", response_model=schemas.ConversationOut)
def create_conversation(
    conversation: schemas.ConversationCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_active_subscription),
):
    # Get the request and its owner
    request = (
        db.query(models.Request)
        .join(models.User)
        .filter(models.Request.id == conversation.request_id)
        .first()
    )

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Verify user roles
    if current_user.user_type == models.UserType.client:
        if request.user_id == current_user.id:
            raise HTTPException(status_code=400, detail="You cannot respond to your own request")
        raise HTTPException(status_code=403, detail="Only developers can initiate conversations")

    if current_user.user_type == models.UserType.developer:
        if request.user.user_type != models.UserType.client:
            raise HTTPException(status_code=400, detail="Can only respond to client requests")

    # Check if conversation already exists
    existing_conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.request_id == conversation.request_id,
            models.Conversation.starter_user_id == current_user.id,
            models.Conversation.recipient_user_id == request.user_id,
        )
        .first()
    )

    if existing_conversation:
        return existing_conversation

    # Create new conversation
    new_conversation = models.Conversation(
        request_id=conversation.request_id,
        starter_user_id=current_user.id,
        recipient_user_id=request.user_id,
        status="active",
    )

    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    # If there's an initial message, create it
    if conversation.initial_message:
        initial_message = models.ConversationMessage(
            conversation_id=new_conversation.id,
            user_id=current_user.id,
            content=conversation.initial_message,
        )
        db.add(initial_message)

        # Create video links if any
        if conversation.video_ids:
            # Verify all videos belong to the user
            videos = (
                db.query(models.Video)
                .filter(
                    models.Video.id.in_(conversation.video_ids),
                    models.Video.user_id == current_user.id,
                )
                .all()
            )

            if len(videos) != len(conversation.video_ids):
                raise HTTPException(
                    status_code=400, detail="One or more videos not found or not owned by user"
                )

            for video_id in conversation.video_ids:
                video_link = models.ConversationVideoLink(
                    conversation_id=new_conversation.id,
                    message_id=initial_message.id,
                    video_id=video_id,
                )
                db.add(video_link)

        # Add profile link if requested
        if conversation.include_profile:
            profile_link = models.ConversationProfileLink(
                conversation_id=new_conversation.id,
                message_id=initial_message.id,
                user_id=current_user.id,
            )
            db.add(profile_link)

        db.commit()

    return new_conversation


@router.get("/{id}", response_model=schemas.ConversationWithMessages)
def get_conversation(
    id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    conversation = db.query(models.Conversation).filter(models.Conversation.id == id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if user is part of the conversation
    if current_user.id not in [conversation.starter_user_id, conversation.recipient_user_id]:
        raise HTTPException(status_code=403, detail="Not authorized to view this conversation")

    # Get user information
    starter = db.query(models.User).filter(models.User.id == conversation.starter_user_id).first()
    recipient = (
        db.query(models.User).filter(models.User.id == conversation.recipient_user_id).first()
    )

    # Get request information
    request = db.query(models.Request).filter(models.Request.id == conversation.request_id).first()

    # Add all required information to the response
    conversation_data = {
        "id": conversation.id,
        "request_id": conversation.request_id,
        "starter_user_id": conversation.starter_user_id,
        "recipient_user_id": conversation.recipient_user_id,
        "starter_username": starter.username,
        "recipient_username": recipient.username,
        "status": conversation.status,
        "created_at": conversation.created_at,  # Add this
        "request_title": request.title if request else "Unknown Request",  # Add this
        "messages": [
            {
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "user_id": msg.user_id,
                "content": msg.content,
                "created_at": msg.created_at,
            }
            for msg in conversation.messages
        ],
    }

    return conversation_data


@router.post("/{id}/messages", response_model=schemas.ConversationMessageOut)
def create_message(
    id: int,
    message: schemas.ConversationMessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    conversation = db.query(models.Conversation).filter(models.Conversation.id == id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if user is part of the conversation
    if current_user.id not in [conversation.starter_user_id, conversation.recipient_user_id]:
        raise HTTPException(status_code=403, detail="Not authorized to post in this conversation")

    new_message = models.ConversationMessage(
        conversation_id=id, user_id=current_user.id, content=message.content
    )

    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    return new_message


@router.get("/user/list", response_model=List[schemas.ConversationWithMessages])
def list_user_conversations(
    request_id: int = None,  # Make request_id optional
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    query = db.query(models.Conversation).filter(
        or_(
            models.Conversation.starter_user_id == current_user.id,
            models.Conversation.recipient_user_id == current_user.id,
        )
    )

    # If request_id is provided, filter conversations for that specific request
    if request_id:
        query = query.filter(models.Conversation.request_id == request_id)

    conversations = query.order_by(models.Conversation.created_at.desc()).all()

    # Fetch request details and messages for each conversation
    result = []
    for conv in conversations:
        # Get the request
        request = db.query(models.Request).filter(models.Request.id == conv.request_id).first()

        # Get all messages
        messages = (
            db.query(models.ConversationMessage)
            .filter(models.ConversationMessage.conversation_id == conv.id)
            .order_by(models.ConversationMessage.created_at)
            .all()
        )

        # Get usernames
        starter = db.query(models.User).filter(models.User.id == conv.starter_user_id).first()
        recipient = db.query(models.User).filter(models.User.id == conv.recipient_user_id).first()

        conv_data = {
            "id": conv.id,
            "request_id": conv.request_id,
            "starter_user_id": conv.starter_user_id,
            "recipient_user_id": conv.recipient_user_id,
            "starter_username": starter.username,
            "recipient_username": recipient.username,
            "status": conv.status,
            "created_at": conv.created_at,
            "messages": messages,
            "request_title": request.title if request else "Unknown Request",
        }
        result.append(conv_data)

    return result


@router.patch("/{id}", response_model=schemas.ConversationOut)
def update_conversation(
    id: int,
    conversation_update: schemas.ConversationUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    # Query for the conversation
    conversation = db.query(models.Conversation).filter(models.Conversation.id == id).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if user is part of the conversation
    if current_user.id not in [conversation.starter_user_id, conversation.recipient_user_id]:
        raise HTTPException(status_code=403, detail="Not authorized to update this conversation")

    # Update the conversation status
    conversation.status = conversation_update.status

    db.commit()
    db.refresh(conversation)

    return conversation


@router.post("/from-video/", response_model=schemas.ConversationOut)
def create_conversation_from_video(
    conversation_data: schemas.ConversationFromVideo,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    # Get the video and its owner
    video = db.query(models.Video).filter(models.Video.id == conversation_data.video_id).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Verify the current user is a client
    if current_user.user_type != models.UserType.client:
        raise HTTPException(status_code=403, detail="Only clients can initiate video conversations")

    # Create a request for this video conversation
    request = models.Request(
        title=conversation_data.title,
        content=conversation_data.content,
        user_id=current_user.id,
        is_public=True,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    # Create the conversation
    new_conversation = models.Conversation(
        request_id=request.id,
        starter_user_id=current_user.id,
        recipient_user_id=video.user_id,
        status="active",
    )

    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    return new_conversation
