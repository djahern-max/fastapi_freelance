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
import traceback

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
            raise HTTPException(
                status_code=400, detail="User already has an active subscription"
            )

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
        logger.info("----------------")
        logger.info("Webhook received")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request headers: {dict(request.headers)}")  # Add this

        payload = await request.body()
        logger.info(f"Received webhook payload of size: {len(payload)}")

        sig_header = request.headers.get("stripe-signature")
        logger.info(f"Stripe signature present: {bool(sig_header)}")
        if sig_header:
            logger.info(f"Signature starts with: {sig_header[:10]}")  # Add this

        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        logger.info(
            f"Using webhook secret starting with: {webhook_secret[:4] if webhook_secret else 'None'}"
        )

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            logger.info(f"Successfully constructed event of type: {event['type']}")
            logger.info(f"Event data: {event['data']['object']}")  # Add this
        except Exception as e:
            logger.error(f"Failed to construct event: {str(e)}")
            logger.error(f"Payload received: {payload.decode()}")  # Add this
            raise

        # Handle subscription events
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            subscription_id = session.get("subscription")

            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                customer_id = session["customer"]
                user_id = int(session["metadata"]["user_id"])

                current_period_end = datetime.fromtimestamp(
                    subscription.current_period_end
                ).replace(tzinfo=timezone("UTC"))

                # Update or create subscription
                existing_subscription = (
                    db.query(models.Subscription)
                    .filter(models.Subscription.user_id == user_id)
                    .first()
                )

                if existing_subscription:
                    existing_subscription.stripe_subscription_id = subscription_id
                    existing_subscription.status = "active"
                    existing_subscription.current_period_end = current_period_end
                    existing_subscription.updated_at = datetime.now(timezone("UTC"))
                else:
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
                    logger.info(
                        f"Successfully processed subscription for user {user_id}"
                    )
                except SQLAlchemyError as e:
                    db.rollback()
                    logger.error(f"Database error processing subscription: {str(e)}")
                    raise HTTPException(
                        status_code=500, detail="Error processing subscription"
                    )

        # Handle payment events
        elif event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            logger.info(f"Payment succeeded: {payment_intent.id}")

        elif event["type"] == "payment_intent.payment_failed":
            payment_intent = event["data"]["object"]
            logger.error(f"Payment failed: {payment_intent.id}")

        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        logger.error(traceback.format_exc())
        # Add request details in case of error
        logger.error(f"Request URL: {request.url}")
        logger.error(f"Request method: {request.method}")
        logger.error(f"Request headers: {dict(request.headers)}")
        raise


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


@router.post("/create-payment-intent")
async def create_payment_intent(
    amount: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        logger.info(
            f"Creating payment intent for user {current_user.id} with amount {amount}"
        )

        # Create a PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="usd",
            customer=current_user.stripe_customer_id,
            metadata={"user_id": str(current_user.id)},
        )

        logger.info(f"Successfully created payment intent: {intent.id}")

        return {"clientSecret": intent.client_secret, "paymentIntentId": intent.id}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm-payment")
async def confirm_payment(
    payment_intent_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if payment_intent.customer != current_user.stripe_customer_id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        return {"status": payment_intent.status}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create-checkout-session")
async def create_checkout_session(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        # Get product and developer details
        product = (
            db.query(models.Product).filter(models.Product.id == product_id).first()
        )
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        developer = (
            db.query(models.User).filter(models.User.id == product.developer_id).first()
        )
        if not developer or not developer.stripe_connect_id:
            raise HTTPException(
                status_code=400, detail="Developer not configured for payments"
            )

        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(product.price * 100),  # Convert to cents
                        "product_data": {
                            "name": product.name,
                            "description": product.description,
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{os.getenv('FRONTEND_URL')}/purchase/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/products/{product_id}",
            payment_intent_data={
                "application_fee_amount": int(product.price * 10),  # 10% platform fee
                "transfer_data": {
                    "destination": developer.stripe_connect_id,
                },
            },
            metadata={
                "product_id": str(product_id),
                "buyer_id": str(current_user.id),
                "developer_id": str(developer.id),
            },
        )

        return {"url": session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{product_id}/purchase")
async def purchase_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        # Get product details
        product = (
            db.query(models.Product).filter(models.Product.id == product_id).first()
        )
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Get developer details
        developer = (
            db.query(models.User).filter(models.User.id == product.developer_id).first()
        )
        if not developer or not developer.stripe_connect_id:
            raise HTTPException(
                status_code=400, detail="Developer not configured for payments"
            )

        # Calculate amounts
        base_amount = int(product.price * 100)  # Convert to cents
        platform_fee = int(base_amount * 0.05)  # 5% platform fee
        total_amount = base_amount + platform_fee

        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": total_amount,
                        "product_data": {
                            "name": product.name,
                            "description": (
                                product.description[:255]
                                if product.description
                                else None
                            ),
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{os.getenv('FRONTEND_URL')}/marketplace/purchase/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/marketplace/products/{product_id}",
            payment_intent_data={
                "application_fee_amount": platform_fee,
                "transfer_data": {
                    "destination": developer.stripe_connect_id,
                },
            },
            metadata={
                "product_id": str(product_id),
                "buyer_id": str(current_user.id),
                "developer_id": str(product.developer_id),
            },
        )

        return {"url": session.url}

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")
