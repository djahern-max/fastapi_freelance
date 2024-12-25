import os
import sys
from pathlib import Path

# Add the parent directory to Python path
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

# Set required environment variables for testing
os.environ.update(
    {
        # Database configuration
        "DATABASE_HOSTNAME": "localhost",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "fastapi",  # Updated to correct database name
        "DATABASE_USERNAME": "postgres",
        "DATABASE_PASSWORD": "password",  # Update if your password is different
        # Auth configuration
        "SECRET_KEY": "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        # Digital Ocean Spaces configuration
        "SPACES_NAME": "ryzevideosv3",
        "SPACES_REGION": "nyc3",
        "SPACES_BUCKET": "ryzevideosv3",
        "SPACES_KEY": "DO00P4DXX6A88URVKEAU",
        "SPACES_SECRET": "vrEqN3UasSoJhrGc6eVtdMwG1Y2myGCkdoh+gE7hBJI",
        "SPACES_ENDPOINT": "https://nyc3.digitaloceanspaces.com",
        # Stripe configuration
        "STRIPE_SECRET_KEY": "your_stripe_test_key",  # Update this
        "STRIPE_WEBHOOK_SECRET": "your_stripe_webhook_secret",  # Update this
        "FRONTEND_URL": "http://localhost:3000",
    }
)

import asyncio
import logging
from fastapi.testclient import TestClient
from app.main import app
from app.oauth2 import create_access_token
from app.database import get_db, SessionLocal
from app.models import User
import stripe
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a new database session for testing
db = SessionLocal()


def get_test_token():
    """Get a valid test token for a developer user"""
    try:
        # Find a developer user
        developer = db.query(User).filter(User.user_type == "developer").first()
        if not developer:
            logger.error("No developer user found in database")
            logger.info(
                "Please ensure there is at least one user with user_type='developer' in the database"
            )
            return None

        # Create a new token
        access_token = create_access_token(data={"user_id": developer.id})
        logger.info(f"Created test token for user ID: {developer.id}")
        return access_token
    except Exception as e:
        logger.error(f"Error creating test token: {str(e)}")
        return None


# Get a fresh token
TEST_USER_TOKEN = get_test_token()
if not TEST_USER_TOKEN:
    raise Exception("Failed to get test token")

TEST_PRODUCT_NAME = "Test AI Product"
TEST_PRODUCT_PRICE = 20.00

client = TestClient(app)


async def test_marketplace_flow():
    """Test the entire marketplace flow from product creation to download"""

    headers = {
        "Authorization": f"Bearer {TEST_USER_TOKEN}",
        "Content-Type": "application/json",
    }

    logger.info("1. Creating test product...")
    product_data = {
        "name": TEST_PRODUCT_NAME,
        "description": "Test Description for AI Product",
        "long_description": "Detailed test description for AI product with complete features",
        "price": TEST_PRODUCT_PRICE,
        "category": "automation",
    }

    try:
        logger.info("Making request to create product...")
        logger.info(f"Using token for authorization: {TEST_USER_TOKEN[:20]}...")
        logger.info(f"Product data: {json.dumps(product_data, indent=2)}")

        response = client.post(
            "/marketplace/products", json=product_data, headers=headers
        )

        if response.status_code != 200:
            logger.error(
                f"Failed to create product. Status code: {response.status_code}"
            )
            logger.error(f"Response: {response.text}")
            return

        product = response.json()
        product_id = product["id"]
        logger.info(f"Product created successfully with ID: {product_id}")
        logger.info(f"Full product details: {json.dumps(product, indent=2)}")

    except Exception as e:
        logger.error(f"Failed to create product: {str(e)}")
        if hasattr(e, "response"):
            logger.error(f"Response content: {e.response.content}")
        return

    logger.info("\n2. Testing purchase flow...")
    try:
        response = client.post(
            f"/marketplace/products/{product_id}/purchase", headers=headers
        )
        if response.status_code != 200:
            logger.error(
                f"Failed to create purchase session. Status code: {response.status_code}"
            )
            logger.error(f"Response: {response.text}")
            return

        checkout_data = response.json()
        logger.info(f"Purchase session created successfully")
        logger.info(f"Checkout URL: {checkout_data['url']}")

        # Calculate expected prices
        base_price = TEST_PRODUCT_PRICE
        platform_fee = base_price * 0.05
        total_price = base_price + platform_fee

        logger.info(f"Price breakdown:")
        logger.info(f"Base price: ${base_price:.2f}")
        logger.info(f"Platform fee (5%): ${platform_fee:.2f}")
        logger.info(f"Total price: ${total_price:.2f}")

    except Exception as e:
        logger.error(f"Failed to create purchase session: {str(e)}")
        if hasattr(e, "response"):
            logger.error(f"Response content: {e.response.content}")
        return

    logger.info("\nTest completed successfully!")
    logger.info("\nTo complete the purchase flow:")
    logger.info("1. Visit the checkout URL provided above")
    logger.info("2. Use test card number: 4242 4242 4242 4242")
    logger.info("3. Use any future date for expiry")
    logger.info("4. Use any 3 digits for CVC")

    return product_id


if __name__ == "__main__":
    try:
        # Close the database session when done
        asyncio.run(test_marketplace_flow())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        logger.exception(e)
    finally:
        db.close()
