import httpx
import logging
from sqlalchemy.orm import Session
from datetime import datetime
from .. import models
from ..config import settings

logger = logging.getLogger(__name__)


async def send_message_to_analytics_hub(
    db: Session, request_id: int, message_id: int, content: str
):
    """Send a message from RYZE.ai to Analytics Hub"""
    try:
        # Get the request to find external ticket details
        request = (
            db.query(models.Request).filter(models.Request.id == request_id).first()
        )
        if not request:
            logger.error(f"Request {request_id} not found")
            return None

        # Check for external metadata
        if not request.external_metadata or not isinstance(
            request.external_metadata, dict
        ):
            logger.error(
                f"Request {request_id} has invalid external metadata: {request.external_metadata}"
            )
            return None

        # Extract the Analytics Hub conversation ID
        # Look for it in the external_metadata
        external_ticket_id = request.external_metadata.get("ticket_id")
        if not external_ticket_id:
            # If not found, use the request ID as a fallback
            logger.warning(
                f"No Analytics Hub ticket ID found in metadata, using request ID as fallback"
            )
            external_ticket_id = str(request_id)

        # Prepare the payload
        payload = {
            "message_id": str(message_id),
            "content": content,
            "sender_type": "support",
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Get API settings from configuration
        api_url = getattr(
            settings, "ANALYTICS_HUB_API_URL", "https://analytics-hub.xyz/api"
        )
        api_key = getattr(settings, "ANALYTICS_HUB_API_KEY", settings.EXTERNAL_API_KEY)

        # The correct endpoint based on Analytics Hub's router
        endpoint = f"{api_url}/support/tickets/{external_ticket_id}/messages"

        logger.info(
            f"Sending message to Analytics Hub: URL={endpoint}, Payload={payload}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint,
                headers={"Content-Type": "application/json", "X-API-Key": api_key},
                json=payload,
                timeout=10.0,
            )

            # Check response
            response.raise_for_status()

            # Update message sync status
            message = (
                db.query(models.ConversationMessage)
                .filter(models.ConversationMessage.id == message_id)
                .first()
            )
            if message:
                # You may need to add these fields to your ConversationMessage model
                # Set a flag to indicate this message was sent to Analytics Hub
                message.external_sync_status = "synced"
                message.external_sync_time = datetime.utcnow()
                db.commit()

            logger.info(
                f"Successfully sent message {message_id} to Analytics Hub ticket {external_ticket_id}"
            )
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error from Analytics Hub: {e.response.status_code} - {e.response.text}"
        )
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error sending to Analytics Hub: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Failed to send message to Analytics Hub: {str(e)}")
        return None
