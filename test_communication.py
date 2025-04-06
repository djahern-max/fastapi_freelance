# test_communication.py
import asyncio
import httpx
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.external_service import send_message_to_analytics_hub
from app import models


async def test_message_sending():
    # Get database session
    db = next(get_db())

    # Find a real external support ticket request
    # This should be a request that was created from an Analytics Hub submission
    requests = (
        db.query(models.Request)
        .filter(models.Request.external_metadata.is_not(None))
        .order_by(models.Request.created_at.desc())
        .limit(5)
        .all()
    )

    if not requests:
        print("No requests with external metadata found")
        return

    # Print the requests for selection
    print("Recent requests with external metadata:")
    for i, req in enumerate(requests):
        title = req.title[:50] + "..." if len(req.title) > 50 else req.title
        print(f"{i+1}. ID: {req.id} - {title}")

    # Select a request or use the most recent one
    selected = 0  # Use the first (most recent) by default
    request = requests[selected]

    # Create a new message in this conversation
    # First find the conversation
    conversation = (
        db.query(models.Conversation)
        .filter(models.Conversation.request_id == request.id)
        .first()
    )

    if not conversation:
        print(f"No conversation found for request {request.id}")
        return

    # Create a test message
    message = models.ConversationMessage(
        conversation_id=conversation.id,
        user_id=1,  # Adjust this to a valid user ID
        content="This is a test message sent programmatically to Analytics Hub",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    print(f"Created message with ID {message.id} in conversation {conversation.id}")

    # Try sending the message
    print(f"Sending message to Analytics Hub for request ID {request.id}...")
    print(f"External metadata: {request.external_metadata}")

    result = await send_message_to_analytics_hub(
        db, request_id=request.id, message_id=message.id, content=message.content
    )

    print(f"Result: {result}")


# Run the test
if __name__ == "__main__":
    asyncio.run(test_message_sending())
