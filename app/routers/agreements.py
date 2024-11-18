from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app import database, models, schemas
from app.database import get_db
from app.oauth2 import get_current_user
from datetime import datetime

router = APIRouter(prefix="/agreements", tags=["Agreements"])


@router.post("/", response_model=schemas.Agreement)
def create_agreement(
    agreement: schemas.AgreementCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Verify the request exists
    request = db.query(models.Request).filter(models.Request.id == agreement.request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Create initial negotiation history entry
    initial_history = {
        "action": "proposal",
        "user_id": current_user.id,
        "timestamp": datetime.utcnow().isoformat(),
        "price": agreement.price,
        "terms": agreement.terms,
    }

    # Create agreement
    new_agreement = models.Agreement(
        request_id=agreement.request_id,
        price=agreement.price,
        terms=agreement.terms,
        developer_id=agreement.developer_id,
        client_id=agreement.client_id,
        status="proposed",
        proposed_by=current_user.id,
        proposed_at=datetime.utcnow(),
        negotiation_history=[initial_history],
    )

    try:
        db.add(new_agreement)
        db.commit()
        db.refresh(new_agreement)
        return new_agreement
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/request/{request_id}", response_model=schemas.Agreement)
def get_agreement_by_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    agreement = db.query(models.Agreement).filter(models.Agreement.request_id == request_id).first()

    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")

    # Verify user has permission to view agreement
    if current_user.id not in [agreement.developer_id, agreement.client_id]:
        raise HTTPException(status_code=403, detail="Not authorized to view this agreement")

    return agreement


@router.post("/{agreement_id}/accept", response_model=schemas.Agreement)
def accept_agreement(
    agreement_id: int,
    acceptance: schemas.AgreementAccept,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    agreement = db.query(models.Agreement).filter(models.Agreement.id == agreement_id).first()

    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")

    # Verify user has permission to accept agreement
    if current_user.id not in [agreement.developer_id, agreement.client_id]:
        raise HTTPException(status_code=403, detail="Not authorized to accept this agreement")

    # Update agreement
    agreement.status = "accepted"
    agreement.agreement_date = acceptance.accepted_at

    # Add to negotiation history
    accept_history = {
        "action": "acceptance",
        "user_id": acceptance.accepted_by,
        "timestamp": acceptance.accepted_at.isoformat(),
        "price": agreement.price,
        "terms": agreement.terms,
    }

    agreement.negotiation_history.append(accept_history)

    try:
        db.commit()
        db.refresh(agreement)
        return agreement
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
