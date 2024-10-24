from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
import logging

# Add debug logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Try imports with debug messages
try:
    from app.models import Newsletter
    logger.debug("Successfully imported Newsletter model")
except ImportError as e:
    logger.error(f"Failed to import Newsletter model: {e}")

try:
    from app.schemas import EmailSchema
    logger.debug("Successfully imported EmailSchema")
except ImportError as e:
    logger.error(f"Failed to import EmailSchema: {e}")

router = APIRouter(
    tags=["Newsletter"],
    prefix="/newsletter"
)

@router.post("/subscribe")
def subscribe_to_newsletter(email: EmailSchema, db: Session = Depends(get_db)):
    logger.debug(f"Attempting to subscribe email: {email.email}")
    try:
        # Check if the email already exists
        email_exist = db.query(Newsletter).filter(Newsletter.email == email.email).first()
        if email_exist:
            logger.debug(f"Email {email.email} already exists")
            return {"message": "Already subscribed to the newsletter"}
        
        # Add the new email if it doesn't exist
        new_email = Newsletter(email=email.email)
        db.add(new_email)
        db.commit()
        logger.debug(f"Successfully subscribed email: {email.email}")
        return {"message": "Successfully subscribed to the newsletter"}
    except Exception as e:
        logger.error(f"Error in subscribe_to_newsletter: {e}")
        raise HTTPException(status_code=500, detail=str(e))
