from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.oauth2 import get_current_user
from app import models, schemas
import stripe
from datetime import datetime, timedelta
import os
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/payments", tags=["Payments"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
SUBSCRIPTION_PRICE_ID = os.getenv("STRIPE_PRICE_ID")  # Your $20/month price ID


@router.post("/create-subscription")
async def create_subscription(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    try:
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": SUBSCRIPTION_PRICE_ID,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{os.getenv('FRONTEND_URL')}/subscription/success",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/subscription/cancel",
            metadata={"user_id": current_user.id},
            billing_address_collection="required",
            allow_promotion_codes=True,
        )

        return JSONResponse(content={"url": session.url})
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            db_subscription = models.Subscription(
                user_id=session["metadata"]["user_id"],
                stripe_subscription_id=session["subscription"],
                stripe_customer_id=session["customer"],
                status="active",
                current_period_end=datetime.now() + timedelta(days=30),
            )
            db.add(db_subscription)
            db.commit()

        return {"status": "success"}
    except stripe.error.SignatureVerificationError as e:
        print(f"Signature verification error: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription-status")
async def get_subscription_status(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    subscription = (
        db.query(models.Subscription).filter(models.Subscription.user_id == current_user.id).first()
    )

    if not subscription:
        return {"status": "none"}

    return {"status": subscription.status, "current_period_end": subscription.current_period_end}
