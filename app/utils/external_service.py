# app/utils/external_service.py

import httpx
import os
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


async def send_message_to_analytics_hub(
    db: Session, request_id: int, message_id: int, content: str
) -> bool:
    """
    Send a message from RYZE.ai to Analytics Hub

    Args:
        db: Database session
        request_id: The request ID
        message_id: The message ID
        content: The message content

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the request with external metadata
        from .. import models

        request = (
            db.query(models.Request).filter(models.Request.id == request_id).first()
        )

        if (
            not request
            or not request.external_metadata
            or "analytics_hub_id" not in request.external_metadata
        ):
            logger.error(
                f"Request {request_id} has no analytics_hub_id in external_metadata"
            )
            return False

        analytics_hub_id = request.external_metadata["analytics_hub_id"]

        # Get the message and user details
        message = (
            db.query(models.ConversationMessage)
            .filter(models.ConversationMessage.id == message_id)
            .first()
        )
        if not message:
            logger.error(f"Message {message_id} not found")
            return False

        user = db.query(models.User).filter(models.User.id == message.user_id).first()
        if not user:
            logger.error(f"User for message {message_id} not found")
            return False

        # Prepare the webhook payload
        payload = {
            "analytics_hub_id": analytics_hub_id,
            "content": content,
            "sender": user.username,
        }

        # Get API endpoint and key from environment
        api_url = os.getenv("ANALYTICS_HUB_API_URL", "https://analytics-hub.xyz/api")
        webhook_url = f"{api_url}/webhooks/ryze/messages"
        api_key = os.getenv("ANALYTICS_HUB_API_KEY")

        if not api_key:
            logger.error("ANALYTICS_HUB_API_KEY environment variable not set")
            return False

        # Set up headers
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

        # Make the request
        logger.info(f"Sending message to Analytics Hub webhook: {webhook_url}")
        logger.info(f"Payload: {payload}")

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, headers=headers)

            if response.status_code in (200, 201, 204):
                logger.info(
                    f"Successfully sent message to Analytics Hub. Response: {response.status_code}"
                )
                return True
            else:
                logger.error(
                    f"Failed to send message to Analytics Hub. Status: {response.status_code}, Response: {response.text}"
                )
                return False

    except Exception as e:
        logger.error(f"Exception sending message to Analytics Hub: {str(e)}")
        return False
