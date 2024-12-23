# At the top of your marketplace.py file
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    File,
    UploadFile,
    Request,
    BackgroundTasks,
)
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional, Dict
from .. import models, schemas, database, oauth2
from ..crud import crud_marketplace
from ..database import get_db
import logging
import os
import boto3
from botocore.exceptions import ClientError
import stripe
import shutil
import zipfile
import stripe.error
import hashlib
import pytest


router = APIRouter(prefix="/marketplace", tags=["Marketplace"])
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Initialize S3 client for DigitalOcean Spaces
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("SPACES_ENDPOINT"),
    aws_access_key_id=os.getenv("SPACES_KEY"),
    aws_secret_access_key=os.getenv("SPACES_SECRET"),
)

# Required environment variables
required_env_vars = [
    "SPACES_ENDPOINT",
    "SPACES_KEY",
    "SPACES_SECRET",
    "SPACES_BUCKET",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "FRONTEND_URL",
]

# Environment variable mapping
env_var_mapping = {
    "SPACES_ENDPOINT": "SPACES_ENDPOINT",
    "SPACES_KEY": "SPACES_KEY",
    "SPACES_SECRET": "SPACES_SECRET",
    "SPACES_BUCKET": "SPACES_BUCKET",
    "STRIPE_SECRET_KEY": "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET": "STRIPE_WEBHOOK_SECRET",
    "FRONTEND_URL": "FRONTEND_URL",
}

# Verify all required environment variables are present
missing_vars = []
for required_var in required_env_vars:
    mapped_var = env_var_mapping.get(required_var, required_var)
    if not os.getenv(mapped_var):
        missing_vars.append(required_var)

if missing_vars:
    logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


@router.post("/products/files/{product_id}")
async def upload_product_files(
    product_id: int,
    files: List[UploadFile] = File(...),
    file_type: str = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Upload files for a product"""
    logger.info(f"Starting file upload for product {product_id}")
    logger.info(f"Received files: {[f.filename for f in files]}")
    logger.info(f"File type: {file_type}")

    # Verify product ownership
    product = crud_marketplace.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.developer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload files for this product",
        )

    # File size and content validation
    file_contents = []
    for file in files:
        content = await file.read()
        await file.seek(0)  # Reset file pointer
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File {file.filename} exceeds maximum size of 100MB",
            )
        file_contents.append(content)

    # Add validation for executables
    if file_type == "executable":
        for file in files:
            if not file.filename.endswith((".exe", ".msi", ".zip")):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file type. Only .exe, .msi, and .zip files are allowed for executables",
                )

    temp_dir = f"/tmp/product_{product_id}"
    zip_path = f"/tmp/product_{product_id}.zip"

    try:
        # Create temp directory
        os.makedirs(temp_dir, exist_ok=True)

        # Track file sizes and generate checksums
        file_records = []
        import hashlib

        # Save uploaded files to temp directory and collect metadata
        for idx, file in enumerate(files):
            file_path = os.path.join(temp_dir, file.filename)
            content = file_contents[idx]

            # Calculate checksum
            checksum = hashlib.sha256(content).hexdigest()

            # Save file
            with open(file_path, "wb") as f:
                f.write(content)

            # Prepare database record
            file_records.append(
                {"filename": file.filename, "size": len(content), "checksum": checksum}
            )

        # Create ZIP archive
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, filenames in os.walk(temp_dir):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)

        # Upload ZIP to DigitalOcean Spaces
        s3_path = f"products/{product_id}/product_files.zip"
        try:
            with open(zip_path, "rb") as zip_file:
                s3_client.upload_fileobj(
                    zip_file,
                    os.getenv("SPACES_BUCKET"),
                    s3_path,
                    ExtraArgs={"ACL": "private"},
                )
        except ClientError as e:
            logger.error(f"Failed to upload to DO Spaces: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to storage",
            )

        # Create ProductFile records in database
        for file_record in file_records:
            db_file = models.ProductFile(
                product_id=product_id,
                file_type=file_type,
                file_path=s3_path,
                file_name=file_record["filename"],
                file_size=file_record["size"],
                checksum=file_record["checksum"],
                version=product.version,
                is_active=True,
            )
            db.add(db_file)

        db.commit()
        logger.info(f"Successfully uploaded files for product {product_id}")

        background_tasks.add_task(cleanup_temp_files, temp_dir, zip_path)

        return {
            "message": "Files uploaded successfully",
            "product_id": product_id,
            "file_count": len(files),
            "files": [
                {"name": fr["filename"], "size": fr["size"]} for fr in file_records
            ],
        }

    except Exception as e:
        logger.error(f"Error during file upload: {str(e)}")
        background_tasks.add_task(cleanup_temp_files, temp_dir, zip_path)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process files: {str(e)}",
        )


@router.post("/products", response_model=schemas.ProductOut)
async def create_product(
    product: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Create a new product in the marketplace"""
    try:
        if current_user.user_type != models.UserType.developer:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only developers can create products",
            )

        logger.debug(f"Creating Stripe product for: {product.name}")
        # Create Stripe product and price
        stripe_product = stripe.Product.create(
            name=product.name,
            description=product.description,
        )
        logger.debug(f"Created Stripe product: {stripe_product.id}")

        stripe_price = stripe.Price.create(
            product=stripe_product.id,
            unit_amount=int(product.price * 100),  # Convert to cents
            currency="usd",
        )
        logger.debug(f"Created Stripe price: {stripe_price.id}")

        db_product = models.MarketplaceProduct(
            developer_id=current_user.id,
            name=product.name,
            description=product.description,
            long_description=product.long_description,
            price=product.price,
            category=product.category,
            stripe_product_id=stripe_product.id,
            stripe_price_id=stripe_price.id,
        )

        if product.video_ids:
            videos = (
                db.query(models.Video)
                .filter(
                    models.Video.id.in_(product.video_ids),
                    models.Video.user_id == current_user.id,
                )
                .all()
            )
            db_product.related_videos.extend(videos)

        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        return db_product

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product payment information",
        )
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product",
        )


@router.get("/products", response_model=schemas.PaginatedProductResponse)
async def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List products with optional filtering"""
    query = db.query(models.MarketplaceProduct).filter(
        models.MarketplaceProduct.status == models.ProductStatus.PUBLISHED
    )

    if category:
        query = query.filter(models.MarketplaceProduct.category == category)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (models.MarketplaceProduct.name.ilike(search_filter))
            | (models.MarketplaceProduct.description.ilike(search_filter))
        )

    total = query.count()
    products = query.offset(skip).limit(limit).all()

    return {"items": products, "total": total, "skip": skip, "limit": limit}


@router.get("/products/{product_id}", response_model=schemas.ProductOut)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(oauth2.get_optional_user),
):
    """Get a specific product's details"""
    product = (
        db.query(models.MarketplaceProduct)
        .filter(models.MarketplaceProduct.id == product_id)
        .first()
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Increment view count
    product.view_count += 1
    db.commit()

    return product


@router.put("/products/{product_id}", response_model=schemas.ProductOut)
async def update_product(
    product_id: int,
    product_update: schemas.ProductUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Update a product"""
    try:
        product = (
            db.query(models.MarketplaceProduct)
            .filter(
                models.MarketplaceProduct.id == product_id,
                models.MarketplaceProduct.developer_id == current_user.id,
            )
            .first()
        )

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Update Stripe product if name or description changed
        if product_update.name or product_update.description:
            stripe.Product.modify(
                product.stripe_product_id,
                name=product_update.name or product.name,
                description=product_update.description or product.description,
            )

        # Update price if changed
        if product_update.price:
            new_stripe_price = stripe.Price.create(
                product=product.stripe_product_id,
                unit_amount=int(product_update.price * 100),
                currency="usd",
            )
            product.stripe_price_id = new_stripe_price.id

        # Update videos if provided
        if product_update.video_ids is not None:
            videos = (
                db.query(models.Video)
                .filter(
                    models.Video.id.in_(product_update.video_ids),
                    models.Video.user_id == current_user.id,
                )
                .all()
            )
            product.related_videos = videos

        # Update other fields
        update_data = product_update.model_dump(
            exclude_unset=True, exclude={"video_ids"}
        )
        for key, value in update_data.items():
            setattr(product, key, value)

        db.commit()
        db.refresh(product)
        return product

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error updating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product payment information",
        )
    except Exception as e:
        logger.error(f"Error updating product: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product",
        )


@router.post("/products/{product_id}/purchase")
async def purchase_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Create a checkout session for product purchase including 5% commission"""
    product = (
        db.query(models.MarketplaceProduct)
        .filter(
            models.MarketplaceProduct.id == product_id,
            models.MarketplaceProduct.status == models.ProductStatus.PUBLISHED,
        )
        .first()
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Calculate base price and commission
    base_price = int(product.price * 100)  # Convert to cents for Stripe
    commission_rate = 0.05  # 5% commission
    commission_amount = int(base_price * commission_rate)
    total_amount = base_price + commission_amount

    # Create a new price with the commission included
    commission_price = stripe.Price.create(
        unit_amount=total_amount,
        currency="usd",
        product=product.stripe_product_id,
        metadata={
            "base_price": base_price,
            "commission_amount": commission_amount,
            "commission_rate": "5%",
        },
    )

    # Create Stripe checkout session
    session = stripe.checkout.Session.create(
        customer=current_user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[
            {
                "price": commission_price.id,
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=f"{os.getenv('FRONTEND_URL')}/marketplace/purchase/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{os.getenv('FRONTEND_URL')}/marketplace/products/{product_id}",
        metadata={
            "product_id": str(product_id),
            "user_id": str(current_user.id),
            "base_price": str(base_price),
            "commission_amount": str(commission_amount),
            "total_amount": str(total_amount),
        },
    )

    return {"url": session.url}


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhooks for marketplace purchases"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # Record the purchase
        product_id = int(session["metadata"]["product_id"])
        user_id = int(session["metadata"]["user_id"])

        download = models.ProductDownload(
            product_id=product_id,
            user_id=user_id,
            price_paid=session["amount_total"] / 100,  # Convert from cents
            transaction_id=session["payment_intent"],
        )

        # Update product statistics
        product = db.query(models.MarketplaceProduct).filter_by(id=product_id).first()
        product.download_count += 1

        db.add(download)
        db.commit()

    return {"status": "success"}


@router.post("/products/{product_id}/reviews", response_model=schemas.ProductReviewOut)
async def create_review(
    product_id: int,
    review: schemas.ProductReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Create a review for a purchased product"""
    # Verify user has purchased the product
    purchase = (
        db.query(models.ProductDownload)
        .filter_by(product_id=product_id, user_id=current_user.id)
        .first()
    )

    if not purchase:
        raise HTTPException(
            status_code=403, detail="You must purchase the product before reviewing it"
        )

    # Check for existing review
    existing_review = (
        db.query(models.ProductReview)
        .filter_by(product_id=product_id, user_id=current_user.id)
        .first()
    )

    if existing_review:
        raise HTTPException(
            status_code=400, detail="You have already reviewed this product"
        )

    # Create review
    db_review = models.ProductReview(
        product_id=product_id, user_id=current_user.id, **review.model_dump()
    )
    db.add(db_review)

    # Update product rating
    product = db.query(models.MarketplaceProduct).filter_by(id=product_id).first()
    reviews = db.query(models.ProductReview).filter_by(product_id=product_id).all()
    product.rating = sum(r.rating for r in reviews) / len(reviews)

    db.commit()
    db.refresh(db_review)
    return db_review


@router.get(
    "/products/{product_id}/reviews", response_model=List[schemas.ProductReviewOut]
)
async def list_reviews(
    product_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List reviews for a product"""
    reviews = (
        db.query(models.ProductReview)
        .filter_by(product_id=product_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return reviews


@router.get(
    "/developers/{developer_id}/products", response_model=List[schemas.ProductOut]
)
async def list_developer_products(
    developer_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List products by a specific developer"""
    products = (
        db.query(models.MarketplaceProduct)
        .filter(
            models.MarketplaceProduct.developer_id == developer_id,
            models.MarketplaceProduct.status == models.ProductStatus.PUBLISHED,
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return products


async def cleanup_temp_files(temp_dir: str, zip_path: str):
    """Clean up temporary files and directories"""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)
    except Exception as e:
        logger.error(f"Error cleaning up temporary files: {str(e)}")


@router.post("/test-product-flow")
async def test_product_flow(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Test the entire product creation and purchase flow"""
    try:
        # 1. Create Stripe product
        stripe_product = stripe.Product.create(
            name="Test AI Product",
            description="Test Description for AI Product",
        )
        logger.info(f"Created Stripe product: {stripe_product.id}")

        # 2. Create Stripe price
        stripe_price = stripe.Price.create(
            product=stripe_product.id,
            unit_amount=2000,  # $20.00
            currency="usd",
        )
        logger.info(f"Created Stripe price: {stripe_price.id}")

        # 3. Create database product record
        db_product = models.MarketplaceProduct(
            developer_id=current_user.id,
            name="Test AI Product",
            description="Test Description for AI Product",
            price=20.00,
            category=models.ProductCategory.AUTOMATION,
            stripe_product_id=stripe_product.id,
            stripe_price_id=stripe_price.id,
            status=models.ProductStatus.PUBLISHED,
        )

        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        logger.info(f"Created database product record: {db_product.id}")

        # 4. Test file upload to DO Spaces
        test_content = b"Test content for AI product"
        s3_path = f"products/{db_product.id}/test.txt"

        try:
            s3_client.put_object(
                Bucket=os.getenv("SPACES_BUCKET"),
                Key=s3_path,
                Body=test_content,
                ACL="private",
            )
            logger.info(f"Uploaded test file to DO Spaces: {s3_path}")
        except ClientError as e:
            logger.error(f"DO Spaces upload failed: {str(e)}")
            raise

        # 5. Create database file record
        db_file = models.ProductFile(
            product_id=db_product.id,
            file_type="test",
            file_path=s3_path,
            file_name="test.txt",
            file_size=len(test_content),
            checksum=hashlib.sha256(test_content).hexdigest(),
            version="1.0.0",
            is_active=True,
        )
        db.add(db_file)
        db.commit()
        logger.info("Created database file record")

        # 6. Test purchase flow
        base_price = int(db_product.price * 100)  # Convert to cents
        commission_rate = 0.05
        commission_amount = int(base_price * commission_rate)
        total_amount = base_price + commission_amount

        commission_price = stripe.Price.create(
            unit_amount=total_amount,
            currency="usd",
            product=db_product.stripe_product_id,
            metadata={
                "base_price": base_price,
                "commission_amount": commission_amount,
                "commission_rate": "5%",
            },
        )
        logger.info(f"Created commission price: {commission_price.id}")

        # 7. Create test checkout session
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": commission_price.id,
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=f"{os.getenv('FRONTEND_URL')}/marketplace/purchase/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/marketplace/products/{db_product.id}",
            metadata={
                "product_id": str(db_product.id),
                "user_id": str(current_user.id),
                "base_price": str(base_price),
                "commission_amount": str(commission_amount),
                "total_amount": str(total_amount),
            },
        )
        logger.info("Created checkout session")

        return {
            "success": True,
            "message": "Test flow completed successfully",
            "data": {
                "product": {
                    "id": db_product.id,
                    "stripe_product_id": stripe_product.id,
                    "stripe_price_id": stripe_price.id,
                },
                "file": {"path": s3_path, "size": len(test_content)},
                "purchase": {
                    "base_price": base_price / 100,  # Convert back to dollars
                    "commission": commission_amount / 100,
                    "total": total_amount / 100,
                    "checkout_url": session.url,
                },
            },
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in test flow: {str(e)}")
        # Clean up any created resources
        if "db_product" in locals():
            db.delete(db_product)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}",
        )
    except ClientError as e:
        logger.error(f"DO Spaces error in test flow: {str(e)}")
        # Clean up any created resources
        if "db_product" in locals():
            db.delete(db_product)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in test flow: {str(e)}")
        # Clean up any created resources
        if "db_product" in locals():
            db.delete(db_product)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test flow failed: {str(e)}",
        )
