from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.oauth2 import get_current_user
from app import models, schemas
import stripe
from datetime import datetime, timedelta
import os
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from pytz import timezone

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
SUBSCRIPTION_PRICE_ID = os.getenv("STRIPE_PRICE_ID")


@router.post("/create-subscription")
async def create_subscription(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    try:
        # First, check if user already has an active subscription
        existing_subscription = (
            db.query(models.Subscription)
            .filter(
                models.Subscription.user_id == current_user.id,
                models.Subscription.status == "active",
            )
            .first()
        )

        if existing_subscription:
            raise HTTPException(status_code=400, detail="User already has an active subscription")

        print(f"Creating subscription for user: {current_user.id}")
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": SUBSCRIPTION_PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=f"{os.getenv('FRONTEND_URL')}/subscription/success",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/subscription/cancel",
            metadata={"user_id": str(current_user.id)},
            billing_address_collection="required",
            allow_promotion_codes=True,
        )
        print(f"Checkout session created: {session.id}")
        return JSONResponse(content={"url": session.url})
    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )

        print(f"Received webhook event: {event['type']}")

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]

            # Retrieve the subscription details
            subscription_id = session.get("subscription")
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                customer_id = session["customer"]
                user_id = int(session["metadata"]["user_id"])

                # Get current period end from subscription
                current_period_end = datetime.fromtimestamp(
                    subscription.current_period_end
                ).replace(tzinfo=timezone("UTC"))

                # Check for existing subscription
                existing_subscription = (
                    db.query(models.Subscription)
                    .filter(models.Subscription.user_id == user_id)
                    .first()
                )

                if existing_subscription:
                    # Update existing subscription
                    existing_subscription.stripe_subscription_id = subscription_id
                    existing_subscription.status = "active"
                    existing_subscription.current_period_end = current_period_end
                    existing_subscription.updated_at = datetime.now(timezone("UTC"))
                else:
                    # Create new subscription
                    db_subscription = models.Subscription(
                        user_id=user_id,
                        stripe_subscription_id=subscription_id,
                        stripe_customer_id=customer_id,
                        status="active",
                        current_period_end=current_period_end,
                    )
                    db.add(db_subscription)

                try:
                    db.commit()
                    print(f"Successfully processed subscription for user {user_id}")
                except SQLAlchemyError as e:
                    db.rollback()
                    logger.error(f"Database error processing subscription: {str(e)}")
                    raise HTTPException(status_code=500, detail="Error processing subscription")

        return {"status": "success"}
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription-status")
async def get_subscription_status(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == current_user.id)
        .order_by(models.Subscription.created_at.desc())
        .first()
    )
    print(f"Checking subscription status for user {current_user.id}: {subscription}")

    if not subscription:
        return {"status": "none"}

    # Make both datetimes timezone-aware for comparison
    current_time = datetime.now(timezone("UTC"))
    subscription_end = subscription.current_period_end

    # Ensure subscription_end is timezone-aware
    if subscription_end.tzinfo is None:
        subscription_end = subscription_end.replace(tzinfo=timezone("UTC"))

    if subscription_end < current_time:
        subscription.status = "expired"
        try:
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating subscription status: {str(e)}")
        return {"status": "expired"}

    return {"status": subscription.status, "current_period_end": subscription_end}
