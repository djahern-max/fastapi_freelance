# app/routers/conversations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database, oauth2
from sqlalchemy import or_
from ..middleware import require_active_subscription
from ..database import get_db
from fastapi import status


router = APIRouter(prefix="/conversations", tags=["Conversations"])


# In routers/conversations.py


@router.post("/", response_model=schemas.ConversationOut)
def create_conversation(
    conversation: schemas.ConversationCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_active_subscription),  # Keep this
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

    return new_conversation


@router.post("/{id}/messages", response_model=schemas.ConversationMessageOut)
def create_message(
    id: int,
    message: schemas.ConversationMessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    try:
        # Only check subscription for developers
        if current_user.user_type == models.UserType.developer:
            subscription = (
                db.query(models.Subscription)
                .filter(models.Subscription.user_id == current_user.id)
                .order_by(models.Subscription.created_at.desc())
                .first()
            )

            if not subscription or subscription.status != "active":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Active subscription required for developers to send messages",
                )

        print(
            f"Creating message with video_ids: {message.video_ids} and include_profile: {message.include_profile}"
        )

        # Check if conversation exists and user has access
        conversation = (
            db.query(models.Conversation).filter(models.Conversation.id == id).first()
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if current_user.id not in [
            conversation.starter_user_id,
            conversation.recipient_user_id,
        ]:
            raise HTTPException(
                status_code=403, detail="Not authorized to post in this conversation"
            )

        # Create the new message
        new_message = models.ConversationMessage(
            conversation_id=id, user_id=current_user.id, content=message.content
        )
        db.add(new_message)
        db.flush()  # Get the message ID without committing
        print(f"Created message with ID: {new_message.id}")

        linked_content = []  # Initialize linked_content list

        # Handle video links
        if message.video_ids:
            print(f"Processing video IDs: {message.video_ids}")
            videos = (
                db.query(models.Video)
                .filter(
                    models.Video.id.in_(message.video_ids),
                    models.Video.user_id == current_user.id,
                )
                .all()
            )
            print(f"Found videos: {[(v.id, v.title) for v in videos]}")

            if len(videos) != len(message.video_ids):
                raise HTTPException(
                    status_code=400,
                    detail="One or more videos not found or not owned by user",
                )

            for video in videos:
                content_link = models.ConversationContentLink(
                    conversation_id=id,
                    message_id=new_message.id,
                    content_type="video",
                    content_id=video.id,
                    title=video.title,
                    url=video.file_path,
                )
                db.add(content_link)
                linked_content.append(
                    {
                        "id": video.id,  # We'll update this after commit
                        "type": "video",
                        "content_id": video.id,
                        "title": video.title,
                        "url": video.file_path,
                    }
                )
                print(f"Added video link for video: {video.title}")

        # Handle profile link
        if message.include_profile:
            print("Adding profile link")
            profile_link = models.ConversationContentLink(
                conversation_id=id,
                message_id=new_message.id,
                content_type="profile",
                content_id=current_user.id,
                title=current_user.username,
                url=f"/profile/developer/{current_user.id}",
            )
            db.add(profile_link)
            linked_content.append(
                {
                    "id": current_user.id,  # We'll update this after commit
                    "type": "profile",
                    "content_id": current_user.id,
                    "title": current_user.username,
                    "url": f"/profile/developer/{current_user.id}",
                }
            )
            print(f"Added profile link for user: {current_user.username}")

        # Commit all changes
        db.commit()
        db.refresh(new_message)

        # Update the IDs in linked_content with actual ContentLink IDs
        content_links = (
            db.query(models.ConversationContentLink)
            .filter(models.ConversationContentLink.message_id == new_message.id)
            .all()
        )

        # Map the content links to their respective linked_content entries
        for i, link in enumerate(content_links):
            if i < len(linked_content):
                linked_content[i]["id"] = link.id

        print(f"Final linked_content: {linked_content}")

        response = {
            "id": new_message.id,
            "conversation_id": new_message.conversation_id,
            "user_id": new_message.user_id,
            "content": new_message.content,
            "created_at": new_message.created_at,
            "linked_content": linked_content,
        }

        print(f"Returning response: {response}")
        return response

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/user/list", response_model=List[schemas.ConversationWithMessages])
def list_user_conversations(
    request_id: int = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),  # Change back to basic auth
):
    print(f"Fetching conversations for user {current_user.id}")

    query = db.query(models.Conversation).filter(
        or_(
            models.Conversation.starter_user_id == current_user.id,
            models.Conversation.recipient_user_id == current_user.id,
        )
    )

    if request_id:
        query = query.filter(models.Conversation.request_id == request_id)

    conversations = query.order_by(models.Conversation.created_at.desc()).all()
    print(f"Found {len(conversations)} conversations")

    result = []
    for conv in conversations:
        print(f"\nProcessing conversation {conv.id}")
        request = (
            db.query(models.Request)
            .filter(models.Request.id == conv.request_id)
            .first()
        )
        messages = []

        # Get all messages for this conversation
        conversation_messages = (
            db.query(models.ConversationMessage)
            .filter(models.ConversationMessage.conversation_id == conv.id)
            .all()
        )
        print(f"Found {len(conversation_messages)} messages in conversation {conv.id}")

        for msg in conversation_messages:
            print(f"\nProcessing message {msg.id}")
            # Get content links for this message
            content_links = (
                db.query(models.ConversationContentLink)
                .filter(models.ConversationContentLink.message_id == msg.id)
                .all()
            )
            print(f"Found {len(content_links)} content links for message {msg.id}")

            linked_content = []
            for link in content_links:
                print(
                    f"Processing link: type={link.content_type}, id={link.content_id}"
                )
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
                        print(f"Added video link: {video.title}")
                    else:
                        print(f"Warning: Video {link.content_id} not found")
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
                                "title": f"{user.username}'s Profile",
                                "url": f"/profile/developer/{user.id}",
                            }
                        )
                        print(f"Added profile link for: {user.username}")
                    else:
                        print(f"Warning: User {link.content_id} not found")

            print(
                f"Total linked content items for message {msg.id}: {len(linked_content)}"
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
            "starter_username": starter.username if starter else "Unknown",
            "recipient_username": recipient.username if recipient else "Unknown",
            "status": conv.status,
            "created_at": conv.created_at,
            "messages": messages,
            "request_title": request.title if request else "Unknown Request",
        }
        result.append(conv_data)
        print(f"Completed processing conversation {conv.id}")

    print(f"Returning {len(result)} conversations")
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
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),  # Change back to basic auth
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
