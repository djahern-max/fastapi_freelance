import requests
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from ..config import settings

# Configure logger
logger = logging.getLogger("analytics_hub_integration")
logger.setLevel(logging.DEBUG)

# Create a file handler if possible
try:
    handler = logging.FileHandler("/var/log/ryze/analytics_hub.log")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
except Exception:
    # Fallback to console logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

# Analytics Hub webhook configuration
ANALYTICS_HUB_URL = (
    settings.ANALYTICS_HUB_API_URL
    or "https://analytics-hub.xyz/api/webhooks/ryze/messages"
)
API_KEY = (
    settings.ANALYTICS_HUB_API_KEY or "n4H9Yz1tKdW18fBNjoUqe6Kclz/yP96cTW8DsJo02uk="
)


def send_message_webhook(
    ticket_id: str,
    message_content: str,
    message_id: str,
    sender_type: str = "support",
    sender_name: Optional[str] = None,
    sender_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a webhook notification to Analytics Hub when a message is created in RYZE

    Parameters:
    - ticket_id: The Analytics Hub ticket ID
    - message_content: The content of the message
    - message_id: Unique identifier for the message
    - sender_type: Type of sender (usually "support" for RYZE messages)
    - sender_name: Optional name of the sender
    - sender_id: Optional ID of the sender

    Returns:
    - Response from the webhook call
    """
    logger.info(f"Sending webhook to Analytics Hub for ticket {ticket_id}")

    # Prepare webhook payload
    payload = {
        "analytics_hub_id": str(ticket_id),
        "content": message_content,
        "sender_type": sender_type,
        "message_id": message_id,
    }

    # Add optional fields if provided
    if sender_name:
        payload["sender"] = sender_name
    if sender_id:
        payload["sender_id"] = sender_id

    # Prepare headers
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "RYZE-Webhook/1.0",
    }

    logger.debug(f"Webhook payload: {payload}")
    logger.debug(f"Webhook URL: {ANALYTICS_HUB_URL}")

    # Send the webhook
    try:
        response = requests.post(
            ANALYTICS_HUB_URL,
            json=payload,
            headers=headers,
            timeout=10,  # 10-second timeout
        )

        # Log response
        logger.info(f"Webhook response status: {response.status_code}")
        try:
            response_json = response.json()
            logger.debug(f"Webhook response: {response_json}")
            return response_json
        except Exception as e:
            logger.warning(f"Could not parse response JSON: {str(e)}")
            return {"status": "sent", "response_text": response.text}

    except Exception as e:
        logger.error(f"Error sending webhook to Analytics Hub: {str(e)}")
        return {"status": "error", "message": str(e)}
