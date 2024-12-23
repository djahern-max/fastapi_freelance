import os
import stripe
import boto3
import asyncio
from botocore.exceptions import ClientError


async def test_stripe_setup():
    try:
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

        # Test product creation
        product = stripe.Product.create(
            name="Test Product", description="Test Description"
        )

        # Test price creation
        price = stripe.Price.create(
            product=product.id, unit_amount=2000, currency="usd"
        )

        print(f"Stripe test successful! Product ID: {product.id}, Price ID: {price.id}")
        return True

    except stripe.error.StripeError as e:
        print(f"Stripe Error: {str(e)}")
        return False


async def test_do_spaces():
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("SPACES_ENDPOINT"),
            aws_access_key_id=os.getenv("SPACES_KEY"),
            aws_secret_access_key=os.getenv("SPACES_SECRET"),
        )

        # Test bucket access
        test_content = b"Test content"
        s3_client.put_object(
            Bucket=os.getenv("SPACES_BUCKET"),
            Key="test/test.txt",
            Body=test_content,
            ACL="private",
        )

        print("DO Spaces test successful!")
        return True

    except ClientError as e:
        print(f"DO Spaces Error: {str(e)}")
        return False


async def main():
    print("Testing Stripe setup...")
    stripe_result = await test_stripe_setup()

    print("\nTesting DO Spaces setup...")
    spaces_result = await test_do_spaces()

    if stripe_result and spaces_result:
        print("\nAll integration tests passed!")
    else:
        print("\nSome tests failed. Please check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
