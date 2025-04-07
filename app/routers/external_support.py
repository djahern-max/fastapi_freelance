# app/routers/external_support.py

from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import logging
from datetime import datetime
import secrets
import string
from passlib.context import CryptContext

from .. import models, schemas, oauth2
from ..database import get_db

# Import your settings module
from ..config import settings

# Import your crud module (we'll create this if needed)
from .. import crud
from fastapi import Header

# Set up logging
logger = logging.getLogger(__name__)

# Set up password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Define the router with the appropriate prefix
router = APIRouter(prefix="/api/external/support-tickets", tags=["External Support"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Dict[str, Any])
def create_external_support_ticket(
    ticket: schemas.ExternalSupportTicketCreate = Body(...),
    db: Session = Depends(get_db),
    api_key: str = Depends(oauth2.get_api_key),
):
    """
    Create a new support ticket from an external source (e.g., Analytics Hub)

    This endpoint is protected by an API key and creates a new support ticket
    in the RYZE.ai system as a public request.
    """
    logger.info(
        f"Received external support ticket from {ticket.source} for {ticket.email}"
    )

    try:
        # Try to find the system service account
        system_user = (
            db.query(models.User).filter(models.User.email == "system@ryze.ai").first()
        )

        # If no system user exists, create one
        if not system_user:
            logger.info("System service account not found, creating one")

            # Generate a secure random password
            alphabet = string.ascii_letters + string.digits
            password = "".join(secrets.choice(alphabet) for _ in range(24))

            # Hash the password
            hashed_password = pwd_context.hash(password)

            # Create the system user
            system_user = models.User(
                username="system",
                email="system@ryze.ai",
                full_name="RYZE System",
                password=hashed_password,
                is_active=True,
                terms_accepted=True,
                user_type="developer",  # Set as developer to handle requests
            )

            # Add to database
            db.add(system_user)
            db.commit()
            db.refresh(system_user)
            logger.info(f"Created system service account with ID {system_user.id}")

        # Format the conversation history for human-readable display
        if ticket.conversation_history and isinstance(
            ticket.conversation_history, list
        ):
            conversation_formatted = "## CONVERSATION HISTORY:\n\n"
            for msg in ticket.conversation_history:
                timestamp = (
                    f" ({msg.timestamp})"
                    if hasattr(msg, "timestamp") and msg.timestamp
                    else ""
                )
                conversation_formatted += (
                    f"**{msg.role.upper()}**{timestamp}: {msg.content}\n\n"
                )
        else:
            conversation_formatted = "No conversation history provided"

        # Format the content to include the external support information
        content = f"""
## EXTERNAL SUPPORT TICKET

**Email**: {ticket.email}
**Source**: {ticket.source}
**Platform**: {ticket.platform or 'Not specified'}
**Website ID**: {ticket.website_id or 'Not specified'}

### ISSUE DESCRIPTION:
{ticket.issue}

{conversation_formatted}
"""

        # Create a new request object using your existing model
        new_request = models.Request(
            title=(
                f"Support: {ticket.issue[:50]}..."
                if len(ticket.issue) > 50
                else f"Support: {ticket.issue}"
            ),
            content=content,
            user_id=system_user.id,
            status="open",  # Use your RequestStatus enum value
            is_public=True,
            contains_sensitive_data=False,  # Support tickets are public
            is_idea=False,
            seeks_collaboration=False,
            estimated_budget=None,  # No budget for support tickets
            # Store additional metadata that might be helpful
            request_metadata={  # Updated from metadata to request_metadata
                "ticket_type": "external_support",
                "source": ticket.source,
                "email": ticket.email,
                "platform": ticket.platform,
                "website_id": ticket.website_id,
                "created_at": datetime.utcnow().isoformat(),
            },
            external_metadata={
                "source": ticket.source,
                "website_id": ticket.website_id,
                "email": ticket.email,
                "conversation": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": (
                            msg.timestamp if hasattr(msg, "timestamp") else None
                        ),
                    }
                    for msg in (ticket.conversation_history or [])
                ],
                "submitted_at": datetime.utcnow().isoformat(),
                "analytics_hub_id": ticket.analytics_hub_id,
            },
        )

        db.add(new_request)
        db.commit()
        db.refresh(new_request)

        new_request.external_metadata["ryze_request_id"] = str(new_request.id)
        db.commit()  # Commit again to save the updated metadata

        logger.info(
            f"External support ticket created successfully with ID {new_request.id}"
        )

        # Optionally, create an initial conversation for this ticket
        try:
            # Find the first available developer to assign the ticket to
            developer = (
                db.query(models.User)
                .filter(models.User.user_type == "developer")
                .filter(models.User.is_active == True)
                .filter(models.User.id != system_user.id)  # Not the system user
                .first()
            )

            recipient_id = developer.id if developer else system_user.id

            # Check if a conversation already exists for this request
            existing_conversation = (
                db.query(models.Conversation)
                .filter(models.Conversation.request_id == new_request.id)
                .first()
            )

            if not existing_conversation:
                # Create new conversation only if one doesn't exist
                new_conversation = models.Conversation(
                    request_id=new_request.id,
                    starter_user_id=system_user.id,
                    recipient_user_id=recipient_id,  # Assign to a developer or self
                    status="active",
                )
                db.add(new_conversation)
                db.commit()
                db.refresh(new_conversation)

                # Only create the initial message if we created a new conversation
                # Add an initial message to the conversation
                initial_message = models.ConversationMessage(
                    conversation_id=new_conversation.id,
                    user_id=system_user.id,
                    content=f"Support ticket created from {ticket.source} for {ticket.email}. Please respond within one hour.",
                )
                db.add(initial_message)
                db.commit()

                # Add the customer's message to the conversation
                customer_message = models.ConversationMessage(
                    conversation_id=new_conversation.id,
                    user_id=system_user.id,  # Using system user as proxy for external user
                    content=ticket.issue,  # The actual content from the customer
                    external_source=ticket.source,  # Mark as coming from external source
                )
                db.add(customer_message)
                db.commit()
            else:
                logger.info(
                    f"Using existing conversation with ID {existing_conversation.id} for request {new_request.id}"
                )
                new_conversation = (
                    existing_conversation  # Use the existing conversation
                )

            logger.info(f"Created initial conversation with ID {new_conversation.id}")

        except Exception as conv_error:
            logger.error(f"Error creating initial conversation: {str(conv_error)}")
            # Continue even if conversation creation fails

        # Try to add it to the developer's snagged requests if we found a developer
        if developer and developer.id != system_user.id:
            try:
                # Check if it's already snagged
                existing_snag = (
                    db.query(models.SnaggedRequest)
                    .filter(models.SnaggedRequest.request_id == new_request.id)
                    .filter(models.SnaggedRequest.developer_id == developer.id)
                    .first()
                )

                if not existing_snag:
                    # Create a snagged request entry
                    snagged = models.SnaggedRequest(
                        request_id=new_request.id,
                        developer_id=developer.id,
                        is_active=True,
                    )
                    db.add(snagged)
                    db.commit()
                    logger.info(f"Auto-assigned ticket to developer ID {developer.id}")
            except Exception as snag_error:
                logger.error(f"Error auto-assigning ticket: {str(snag_error)}")
                # Continue even if snagging fails

        return {
            "status": "success",
            "message": "Support ticket created successfully",
            "ticket_id": new_request.id,
        }
    except Exception as e:
        logger.error(f"Error creating external support ticket: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create support ticket: {str(e)}",
        )


# For pre-flight CORS requests
@router.options("/", status_code=status.HTTP_204_NO_CONTENT)
def options_create_external_support_ticket():
    """
    Handle OPTIONS requests for CORS pre-flight check
    """


# In app/routers/external_support.py


@router.post("/{ticket_id}/messages", status_code=201)
def add_external_message(
    ticket_id: int,
    message: schemas.ExternalMessageCreate,
    db: Session = Depends(get_db),  # Add this
    api_key: str = Header(..., alias="X-API-Key"),
):
    # Validate API key
    if api_key != settings.EXTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Get the request by external ticket ID
    db_request = crud.get_request_by_external_id(db, ticket_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Get the conversation associated with this request
    conversation = crud.get_conversation_by_request_id(db, db_request.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Create a new message in the conversation
    new_message = crud.create_conversation_message(
        db,
        conversation_id=conversation.id,
        user_id=db_request.user_id,  # Use request owner as the sender
        content=message.content,
        external_source="analytics-hub",
    )

    return {"id": new_message.id, "status": "created"}
