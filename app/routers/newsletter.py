from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Newsletter
from app.schemas import EmailSchema

router = APIRouter()

@router.post("/subscribe")
def subscribe_to_newsletter(email: EmailSchema, db: Session = Depends(get_db)):
    # Check if the email already exists
    email_exist = db.query(Newsletter).filter(Newsletter.email == email.email).first()
    if email_exist:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Add the new email
    new_email = Newsletter(email=email.email)
    db.add(new_email)
    db.commit()
    return {"message": "Successfully subscribed to the newsletter"}
