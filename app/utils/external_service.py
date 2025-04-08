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

        # Print request_id to verify it's valid
        print(f"Sending message to Analytics Hub for request ID: {request_id}")

        # Check if request_id is valid
        if not request_id:
            logger.error("Invalid request_id (None or 0)")
            return False

        request = (
            db.query(models.Request).filter(models.Request.id == request_id).first()
        )

        # Print request to verify it was found
        print(f"Found request: {request}")

        # Check if request exists
        if not request:
            logger.error(f"Request with ID {request_id} not found")
            return False

        # Check if external_metadata exists
        if (
            not hasattr(request, "external_metadata")
            or request.external_metadata is None
        ):
            logger.error(
                f"Request {request_id} has no external_metadata attribute or it is None"
            )
            return False

        # Print external_metadata to check its type and content
        print(
            f"Request external_metadata: {type(request.external_metadata)} - {request.external_metadata}"
        )

        # Check external_metadata type
        if not isinstance(request.external_metadata, dict):
            try:
                # Try to convert to dict if it's JSON string or similar
                import json

                external_metadata = json.loads(request.external_metadata)
                analytics_hub_id = external_metadata.get("analytics_hub_id")
                if not analytics_hub_id:
                    logger.error(
                        f"analytics_hub_id not found in parsed external_metadata"
                    )
                    return False
            except Exception as e:
                logger.error(f"Failed to parse external_metadata: {str(e)}")
                return False
        else:
            # It's already a dict
            if "analytics_hub_id" not in request.external_metadata:
                logger.error(
                    f"analytics_hub_id not found in external_metadata dictionary"
                )
                return False
            analytics_hub_id = request.external_metadata["analytics_hub_id"]

        # Print analytics_hub_id to verify it's correct
        print(f"Found analytics_hub_id: {analytics_hub_id}")

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
        api_url = os.getenv("ANALYTICS_HUB_API_URL")
        if not api_url:
            logger.error("ANALYTICS_HUB_API_URL environment variable not set")
            # Default to a common value for debugging
            api_url = "http://localhost:8000/api"

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
        print(f"Sending to webhook URL: {webhook_url}")
        print(f"With payload: {payload}")

        # Use a timeout to prevent hanging
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload, headers=headers)

            # Print full response for debugging
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")

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
        # Print exception traceback for debugging
        import traceback

        print(f"Exception sending message to Analytics Hub: {str(e)}")
        print(traceback.format_exc())
        return False
