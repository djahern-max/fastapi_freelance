# app/routers/conversations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database, oauth2
from sqlalchemy import or_
from ..middleware import require_active_subscription
from ..database import get_db


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
            raise HTTPException(
                status_code=400, detail="You cannot respond to your own request"
            )
        raise HTTPException(
            status_code=403, detail="Only developers can initiate conversations"
        )

    if current_user.user_type == models.UserType.developer:
        if request.user.user_type != models.UserType.client:
            raise HTTPException(
                status_code=400, detail="Can only respond to client requests"
            )

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

    # If there's an initial message, create it with any linked content
    if conversation.initial_message:
        message = models.ConversationMessage(
            conversation_id=new_conversation.id,
            user_id=current_user.id,
            content=conversation.initial_message,
        )
        db.add(message)
        db.flush()  # Get message ID without committing

        # Add video links if any are provided
        if conversation.video_ids:
            # Verify videos belong to the user
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
                    status_code=400,
                    detail="One or more videos not found or not owned by user",
                )

            for video_id in conversation.video_ids:
                content_link = models.ConversationContentLink(
                    conversation_id=new_conversation.id,
                    message_id=message.id,
                    content_type="video",
                    content_id=video_id,
                )
                db.add(content_link)

        # Add profile link if requested
        if conversation.include_profile:
            profile_link = models.ConversationContentLink(
                conversation_id=new_conversation.id,
                message_id=message.id,
                content_type="profile",
                content_id=current_user.id,
            )
            db.add(profile_link)

        db.commit()
        db.refresh(message)

    return new_conversation


@router.post("/{id}/messages", response_model=schemas.ConversationMessageOut)
def create_message(
    id: int,
    message: schemas.ConversationMessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        print(f"Creating message for conversation {id}")  # Debug print
        conversation = (
            db.query(models.Conversation).filter(models.Conversation.id == id).first()
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        print(
            f"User ID: {current_user.id}, Conversation starter: {conversation.starter_user_id}, recipient: {conversation.recipient_user_id}"
        )  # Debug print
        if current_user.id not in [
            conversation.starter_user_id,
            conversation.recipient_user_id,
        ]:
            raise HTTPException(
                status_code=403, detail="Not authorized to post in this conversation"
            )

        new_message = models.ConversationMessage(
            conversation_id=id, user_id=current_user.id, content=message.content
        )

        print("Adding new message")  # Debug print
        db.add(new_message)
        db.flush()
        print(f"Created message with ID: {new_message.id}")  # Debug print

        # Add video links if any are provided
        if message.video_ids:
            print(f"Processing video IDs: {message.video_ids}")  # Debug print
            videos = (
                db.query(models.Video)
                .filter(
                    models.Video.id.in_(message.video_ids),
                    models.Video.user_id == current_user.id,
                )
                .all()
            )
            print(f"Found videos: {[v.id for v in videos]}")  # Debug print

            if len(videos) != len(message.video_ids):
                raise HTTPException(
                    status_code=400,
                    detail="One or more videos not found or not owned by user",
                )

            for video in videos:
                print(f"Adding link for video {video.id}")  # Debug print
                content_link = models.ConversationContentLink(
                    conversation_id=id,
                    message_id=new_message.id,
                    content_type="video",
                    content_id=video.id,
                )
                db.add(content_link)

        # Add profile link if requested
        if message.include_profile:
            print("Adding profile link")  # Debug print
            profile_link = models.ConversationContentLink(
                conversation_id=id,
                message_id=new_message.id,
                content_type="profile",
                content_id=current_user.id,
            )
            db.add(profile_link)

        print("Committing changes")  # Debug print
        db.commit()

        print("Fetching message with links")  # Debug print
        message_with_links = (
            db.query(models.ConversationMessage)
            .filter(models.ConversationMessage.id == new_message.id)
            .first()
        )

        # Build linked_content list
        linked_content = []
        print("Processing content links")  # Debug print
        for link in message_with_links.content_links:
            print(
                f"Processing link type: {link.content_type}, id: {link.content_id}"
            )  # Debug print
            if link.content_type == "video":
                video = (
                    db.query(models.Video)
                    .filter(models.Video.id == link.content_id)
                    .first()
                )
                if video:
                    linked_content.append(
                        {
                            "id": link.id,
                            "type": "video",
                            "content_id": video.id,
                            "title": video.title,
                            "url": video.file_path,
                        }
                    )
            elif link.content_type == "profile":
                user = (
                    db.query(models.User)
                    .filter(models.User.id == link.content_id)
                    .first()
                )
                if user:
                    linked_content.append(
                        {
                            "id": link.id,
                            "type": "profile",
                            "content_id": user.id,
                            "title": user.username,
                            "url": f"/profile/developer/{user.id}",
                        }
                    )

        print("Preparing response")  # Debug print
        response = {
            "id": message_with_links.id,
            "conversation_id": message_with_links.conversation_id,
            "user_id": message_with_links.user_id,
            "content": message_with_links.content,
            "created_at": message_with_links.created_at,
            "linked_content": linked_content,
        }
        print("Returning response")  # Debug print
        return response

    except Exception as e:
        print(f"Error occurred: {str(e)}")  # Debug print
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/user/list", response_model=List[schemas.ConversationWithMessages])
def list_user_conversations(
    request_id: int = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    query = db.query(models.Conversation).filter(
        or_(
            models.Conversation.starter_user_id == current_user.id,
            models.Conversation.recipient_user_id == current_user.id,
        )
    )

    if request_id:
        query = query.filter(models.Conversation.request_id == request_id)

    conversations = query.order_by(models.Conversation.created_at.desc()).all()

    result = []
    for conv in conversations:
        request = (
            db.query(models.Request)
            .filter(models.Request.id == conv.request_id)
            .first()
        )
        messages = []

        for msg in (
            db.query(models.ConversationMessage)
            .filter(models.ConversationMessage.conversation_id == conv.id)
            .all()
        ):
            # Get content links for this message
            content_links = (
                db.query(models.ConversationContentLink)
                .filter(models.ConversationContentLink.message_id == msg.id)
                .all()
            )

            linked_content = []
            for link in content_links:
                if link.content_type == "video":
                    video = (
                        db.query(models.Video)
                        .filter(models.Video.id == link.content_id)
                        .first()
                    )
                    if video:
                        linked_content.append(
                            {
                                "id": link.id,
                                "type": "video",
                                "content_id": video.id,
                                "title": video.title,
                                "url": video.file_path,
                            }
                        )
                elif link.content_type == "profile":
                    dev_profile = (
                        db.query(models.DeveloperProfile)
                        .filter(models.DeveloperProfile.user_id == link.content_id)
                        .first()
                    )
                    if dev_profile:
                        linked_content.append(
                            {
                                "id": link.id,
                                "type": "profile",
                                "content_id": dev_profile.user_id,
                                "title": f"Developer Profile",
                                "url": f"/profile/developer/{dev_profile.user_id}",
                            }
                        )

            messages.append(
                {
                    "id": msg.id,
                    "conversation_id": msg.conversation_id,
                    "user_id": msg.user_id,
                    "content": msg.content,
                    "created_at": msg.created_at,
                    "linked_content": linked_content,
                }
            )

        starter = (
            db.query(models.User).filter(models.User.id == conv.starter_user_id).first()
        )
        recipient = (
            db.query(models.User)
            .filter(models.User.id == conv.recipient_user_id)
            .first()
        )

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
    video = (
        db.query(models.Video)
        .filter(models.Video.id == conversation_data.video_id)
        .first()
    )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Verify the current user is a client
    if current_user.user_type != models.UserType.client:
        raise HTTPException(
            status_code=403, detail="Only clients can initiate video conversations"
        )

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


@router.get("/{conversation_id}", response_model=schemas.ConversationWithMessages)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            or_(
                models.Conversation.starter_user_id == current_user.id,
                models.Conversation.recipient_user_id == current_user.id,
            ),
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation
