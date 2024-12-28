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
from ..config import settings
import json

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])

stripe.api_key = settings.stripe_secret_key
SUBSCRIPTION_PRICE_ID = settings.stripe_price_id

logger.info("Starting payment service with configuration:")
logger.info(
    f"Stripe API Key configured: {'Yes' if settings.stripe_secret_key else 'No'}"
)
logger.info(
    f"Webhook Secret configured: {'Yes' if settings.stripe_webhook_secret else 'No'}"
)
logger.info(f"Price ID configured: {'Yes' if settings.stripe_price_id else 'No'}")


@router.post("/create-subscription")
async def create_subscription(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    try:
        # First, ensure customer exists or create them
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email, metadata={"user_id": str(current_user.id)}
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        else:
            # Verify customer exists in Stripe
            try:
                stripe.Customer.retrieve(current_user.stripe_customer_id)
            except stripe.error.InvalidRequestError:
                # Customer doesn't exist in Stripe, create new one
                customer = stripe.Customer.create(
                    email=current_user.email, metadata={"user_id": str(current_user.id)}
                )
                current_user.stripe_customer_id = customer.id
                db.commit()

        # Then create the checkout session
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{settings.frontend_url}/subscription/success",
            cancel_url=f"{settings.frontend_url}/subscription/cancel",
            metadata={"user_id": str(current_user.id)},
            allow_promotion_codes=True,
            billing_address_collection="required",
        )

        return {"url": session.url}

    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        webhook_secret = settings.stripe_webhook_secret

        logger.info(f"Processing webhook with signature: {sig_header}")

        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

        logger.info(f"Webhook event type: {event['type']}")

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            subscription_id = session.get("subscription")

            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                customer_id = session["customer"]
                user_id = int(session["metadata"]["user_id"])

                logger.info(
                    f"Processing subscription {subscription_id} for user {user_id}"
                )

                current_period_end = datetime.fromtimestamp(
                    subscription.current_period_end
                ).replace(tzinfo=timezone("UTC"))

                try:
                    existing_subscription = (
                        db.query(models.Subscription)
                        .filter(models.Subscription.user_id == user_id)
                        .first()
                    )

                    if existing_subscription:
                        existing_subscription.stripe_subscription_id = subscription_id
                        existing_subscription.status = "active"
                        existing_subscription.current_period_end = current_period_end
                    else:
                        db_subscription = models.Subscription(
                            user_id=user_id,
                            stripe_subscription_id=subscription_id,
                            stripe_customer_id=customer_id,
                            status="active",
                            current_period_end=current_period_end,
                        )
                        db.add(db_subscription)

                    db.commit()
                    logger.info(f"Successfully saved subscription for user {user_id}")
                except SQLAlchemyError as e:
                    db.rollback()
                    logger.error(f"Database error: {str(e)}")
                    raise HTTPException(status_code=500, detail="Database error")

        return {"status": "success"}
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Signature verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription-status")
async def get_subscription_status(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    print("============= Subscription Status Check =============")
    print(f"User ID: {current_user.id}")
    print(f"Stripe Customer ID: {current_user.stripe_customer_id}")

    subscription = (
        db.query(models.Subscription)
        .filter(models.Subscription.user_id == current_user.id)
        .order_by(models.Subscription.created_at.desc())
        .first()
    )
    print(f"Database subscription found: {subscription is not None}")

    if not subscription:
        print("No subscription found in database")
        # Let's check Stripe directly
        try:
            if current_user.stripe_customer_id:
                stripe_subs = stripe.Subscription.list(
                    customer=current_user.stripe_customer_id, limit=1, status="active"
                )
                print(f"Stripe subscriptions found: {len(stripe_subs.data)}")
                if stripe_subs.data:
                    print("Active subscription found in Stripe but not in database!")
                    # Could add logic here to sync the subscription
        except Exception as e:
            print(f"Error checking Stripe: {str(e)}")
        return {"status": "none"}

    print(f"Subscription status from DB: {subscription.status}")
    print(f"Subscription end date: {subscription.current_period_end}")

    # Make both datetimes timezone-aware for comparison
    current_time = datetime.now(timezone("UTC"))
    subscription_end = subscription.current_period_end

    # Ensure subscription_end is timezone-aware
    if subscription_end.tzinfo is None:
        subscription_end = subscription_end.replace(tzinfo=timezone("UTC"))

    print(f"Current time (UTC): {current_time}")
    print(f"Subscription end (UTC): {subscription_end}")

    if subscription_end < current_time:
        print("Subscription has expired")
        subscription.status = "expired"
        try:
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            print(f"Database error updating subscription status: {str(e)}")
            logger.error(f"Database error updating subscription status: {str(e)}")
        return {"status": "expired"}

    print(f"Returning status: {subscription.status}")
    return {"status": subscription.status, "current_period_end": subscription_end}


@router.post("/create-payment-intent")
async def create_payment_intent(
    amount: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        # Validate amount
        if amount <= 0:
            logger.error(f"Invalid amount provided: {amount}")
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")

        # Log the attempt
        logger.info(
            f"Creating payment intent - User: {current_user.id}, "
            f"Amount: ${amount/100:.2f}, "
            f"Customer ID: {current_user.stripe_customer_id}"
        )

        # Verify customer exists in Stripe
        try:
            customer = stripe.Customer.retrieve(current_user.stripe_customer_id)
            if customer.get("deleted"):
                logger.error(
                    f"Stripe customer {current_user.stripe_customer_id} was deleted"
                )
                raise HTTPException(status_code=400, detail="Invalid customer account")
        except stripe.error.InvalidRequestError:
            logger.error(
                f"Invalid Stripe customer ID: {current_user.stripe_customer_id}"
            )
            raise HTTPException(status_code=400, detail="Invalid customer account")

        # Create PaymentIntent with detailed metadata
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency="usd",
                customer=current_user.stripe_customer_id,
                metadata={
                    "user_id": str(current_user.id),
                    "user_email": current_user.email,
                    "environment": (
                        "live" if stripe.api_key.startswith("sk_live") else "test"
                    ),
                    "created_at": datetime.now(timezone("UTC")).isoformat(),
                },
                description=f"Payment for user {current_user.email}",
                statement_descriptor="RYZE.AI PAYMENT",
                statement_descriptor_suffix="RYZE",
                capture_method="automatic",
            )

            logger.info(
                f"Payment intent created successfully - "
                f"ID: {intent.id}, "
                f"Amount: ${intent.amount/100:.2f}, "
                f"Status: {intent.status}"
            )

            return {
                "clientSecret": intent.client_secret,
                "paymentIntentId": intent.id,
                "amount": intent.amount,
                "status": intent.status,
            }

        except stripe.error.CardError as e:
            # Card was declined
            logger.error(f"Card error for user {current_user.id}: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "card_error",
                    "message": e.error.message,
                    "code": e.error.code,
                },
            )

        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            logger.error(f"Invalid Stripe request for user {current_user.id}: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_request",
                    "message": "Invalid payment parameters",
                },
            )

        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            logger.error(f"Stripe authentication error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "authentication_error",
                    "message": "Failed to authenticate with payment provider",
                },
            )

        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            logger.error(f"Stripe API connection error: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "api_connection_error",
                    "message": "Could not connect to payment provider",
                },
            )

        except stripe.error.StripeError as e:
            # Generic error
            logger.error(
                f"Unexpected Stripe error for user {current_user.id}: {str(e)}"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "payment_error",
                    "message": "An unexpected error occurred with the payment provider",
                },
            )

    except HTTPException:
        raise

    except Exception as e:
        # Catch any other unexpected errors
        logger.error(
            f"Critical error in create_payment_intent: {str(e)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        raise HTTPException(
            status_code=500,
            detail={"error": "server_error", "message": "An unexpected error occurred"},
        )

    finally:
        # Log the completion of the request
        logger.info(f"Completed payment intent request for user {current_user.id}")


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
