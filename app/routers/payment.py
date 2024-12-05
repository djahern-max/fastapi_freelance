# payment.py in routers folder
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.oauth2 import get_current_user
from app import models, schemas
import stripe
from datetime import datetime, timezone
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
        if current_user.user_type != models.UserType.developer:
            raise HTTPException(status_code=403, detail="Only developers can subscribe")

        existing_sub = (
            db.query(models.Subscription)
            .filter(models.Subscription.user_id == current_user.id)
            .first()
        )

        if existing_sub and existing_sub.status == "active":
            raise HTTPException(status_code=400, detail="User already has an active subscription")

        if not hasattr(current_user, "stripe_customer_id") or not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email, metadata={"user_id": current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.commit()

        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": SUBSCRIPTION_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{os.getenv('FRONTEND_URL')}/subscription/success",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/subscription/cancel",
            metadata={"user_id": current_user.id},
        )

        return JSONResponse(
            content={"session_id": session.id, "url": session.url},
            headers={
                "Access-Control-Allow-Origin": os.getenv("ALLOWED_ORIGINS"),
                "Access-Control-Allow-Credentials": "true",
            },
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event.type == "customer.subscription.created":
        subscription = event.data.object
        user = (
            db.query(models.User)
            .filter(models.User.stripe_customer_id == subscription.customer)
            .first()
        )

        if user:
            db_subscription = models.Subscription(
                user_id=user.id,
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer,
                status=subscription.status,
                current_period_end=datetime.fromtimestamp(
                    subscription.current_period_end, timezone.utc
                ),
            )
            db.add(db_subscription)
            db.commit()

    return {"status": "success"}


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
