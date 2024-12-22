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


router = APIRouter(prefix="/marketplace", tags=["Marketplace"])
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("DO_SPACES_ENDPOINT"),
    aws_access_key_id=os.getenv("DO_SPACES_KEY"),
    aws_secret_access_key=os.getenv("DO_SPACES_SECRET"),
)


@router.post("/products/files/{product_id}")
async def upload_product_files(
    product_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),  # Modified this line
):
    """Upload product files to cloud storage."""
    # Verify product ownership
    product = crud_marketplace.get_product(db, product_id)

    if product.developer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload files for this product",
        )

    temp_dir = f"/tmp/product_{product_id}"
    zip_path = f"/tmp/product_{product_id}.zip"

    try:
        # Create temp directory
        os.makedirs(temp_dir, exist_ok=True)

        # Save uploaded files to temp directory
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

        # Create ZIP archive
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, filenames in os.walk(temp_dir):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)

        # Upload ZIP to DigitalOcean Spaces
        with open(zip_path, "rb") as zip_file:
            s3_client.upload_fileobj(
                zip_file,
                os.getenv("DO_SPACES_BUCKET"),
                f"products/{product_id}/product_files.zip",
                ExtraArgs={"ACL": "private"},
            )

        background_tasks.add_task(cleanup_temp_files, temp_dir, zip_path)

        return {
            "message": "Files uploaded successfully",
            "product_id": product_id,
            "file_count": len(files),
        }

    except Exception as e:
        logger.error(f"Error during file upload: {str(e)}")
        background_tasks.add_task(cleanup_temp_files, temp_dir, zip_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process files: {str(e)}",
        )


@router.get("/products/download/{product_id}")
async def get_download_url(
    product_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Generate temporary download URL for purchased product."""
    # Verify purchase
    purchase = (
        db.query(models.ProductDownload)
        .filter(
            models.ProductDownload.product_id == product_id,
            models.ProductDownload.user_id == current_user.id,
        )
        .first()
    )

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must purchase this product before downloading",
        )

    try:
        # Generate presigned URL valid for 1 hour
        file_key = f"products/{product_id}/product_files.zip"
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.getenv("DO_SPACES_BUCKET"), "Key": file_key},
            ExpiresIn=3600,
        )
        return {"download_url": url}
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}",
        )


@router.post("/products", response_model=schemas.ProductOut)
async def create_product(
    product: schemas.ProductCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Create a new product in the marketplace"""
    if current_user.user_type != models.UserType.developer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only developers can create products",
        )

    # Create Stripe product and price
    stripe_product = stripe.Product.create(
        name=product.name,
        description=product.description,
    )

    stripe_price = stripe.Price.create(
        product=stripe_product.id,
        unit_amount=int(product.price * 100),  # Convert to cents
        currency="usd",
    )

    db_product = models.MarketplaceProduct(
        **product.model_dump(exclude={"video_ids"}),
        developer_id=current_user.id,
        stripe_product_id=stripe_product.id,
        stripe_price_id=stripe_price.id,
    )

    # Add related videos if provided
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
    current_user: Optional[models.User] = Depends(oauth2.get_current_user_optional),
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
    update_data = product_update.model_dump(exclude_unset=True, exclude={"video_ids"})
    for key, value in update_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


@router.post("/products/{product_id}/purchase")
async def purchase_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Create a checkout session for product purchase"""
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

    # Create Stripe checkout session
    session = stripe.checkout.Session.create(
        customer=current_user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[
            {
                "price": product.stripe_price_id,
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=f"{os.getenv('FRONTEND_URL')}/marketplace/purchase/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{os.getenv('FRONTEND_URL')}/marketplace/products/{product_id}",
        metadata={"product_id": str(product_id), "user_id": str(current_user.id)},
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
