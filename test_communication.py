# Create a test script in RYZE.ai (test_communication.py)
import asyncio
import httpx
import logging
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.external_service import send_message_to_analytics_hub


async def test_message_sending():
    # Get database session
    db = next(get_db())

    # Use a known request ID
    request_id = 123  # Replace with an actual request ID from your database
    message_id = 456  # Replace with an actual message ID
    content = "This is a test message from RYZE.ai to Analytics Hub"

    # Try sending the message
    result = await send_message_to_analytics_hub(db, request_id, message_id, content)

    print(f"Result: {result}")


# Run the test
asyncio.run(test_message_sending())
