from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Newsletter
from app.schemas import EmailSchema

router = APIRouter(
    tags=["Newsletter"]
)

@router.post("/subscribe")
def subscribe_to_newsletter(email: EmailSchema, db: Session = Depends(get_db)):
    # Check if the email already exists
    email_exist = db.query(Newsletter).filter(Newsletter.email == email.email).first()
    if email_exist:
        # If the email exists, just return a success message
        return {"message": "Already subscribed to the newsletter"}
    
    # Add the new email if it doesn't exist
    new_email = Newsletter(email=email.email)
    db.add(new_email)
    db.commit()
    return {"message": "Successfully subscribed to the newsletter"}

