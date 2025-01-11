from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional
from .. import models, schemas
from sqlalchemy import func, or_


def create_product(db: Session, product: schemas.ProductCreate, developer_id: int):
    """Create a new marketplace product today."""
    db_product = models.MarketplaceProduct(
        **product.model_dump(exclude={"video_ids"}),
        developer_id=developer_id,
    )

    if product.video_ids:
        videos = (
            db.query(models.Video)
            .filter(
                models.Video.id.in_(product.video_ids),
                models.Video.user_id == developer_id,
            )
            .all()
        )
        db_product.related_videos.extend(videos)

    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def get_product(db: Session, product_id: int) -> models.MarketplaceProduct:
    """Get a specific product by ID."""
    product = (
        db.query(models.MarketplaceProduct)
        .filter(models.MarketplaceProduct.id == product_id)
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return product


def list_products(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    category: Optional[str] = None,
    search: Optional[str] = None,
    developer_id: Optional[int] = None,
) -> List[models.MarketplaceProduct]:
    """List products with optional filtering."""
    query = db.query(models.MarketplaceProduct).filter(
        models.MarketplaceProduct.status == models.ProductStatus.PUBLISHED
    )

    if category:
        query = query.filter(models.MarketplaceProduct.category == category)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                models.MarketplaceProduct.name.ilike(search_filter),
                models.MarketplaceProduct.description.ilike(search_filter),
            )
        )

    if developer_id:
        query = query.filter(models.MarketplaceProduct.developer_id == developer_id)

    return query.offset(skip).limit(limit).all()


def update_product(
    db: Session,
    product_id: int,
    product_update: schemas.ProductUpdate,
    developer_id: int,
) -> models.MarketplaceProduct:
    """Update a product."""
    product = (
        db.query(models.MarketplaceProduct)
        .filter(
            models.MarketplaceProduct.id == product_id,
            models.MarketplaceProduct.developer_id == developer_id,
        )
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or you don't have permission to update it",
        )

    # Update video associations if provided
    if product_update.video_ids is not None:
        videos = (
            db.query(models.Video)
            .filter(
                models.Video.id.in_(product_update.video_ids),
                models.Video.user_id == developer_id,
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


def create_product_download(
    db: Session, product_id: int, user_id: int, price_paid: float, transaction_id: str
) -> models.ProductDownload:
    """Record a product download."""
    download = models.ProductDownload(
        product_id=product_id,
        user_id=user_id,
        price_paid=price_paid,
        transaction_id=transaction_id,
    )

    # Update product download count
    product = get_product(db, product_id)
    product.download_count += 1

    db.add(download)
    db.commit()
    db.refresh(download)
    return download


def create_product_review(
    db: Session, product_id: int, user_id: int, review: schemas.ProductReviewCreate
) -> models.ProductReview:
    """Create a review for a product."""
    # Check if user has purchased the product
    purchase = (
        db.query(models.ProductDownload)
        .filter(
            models.ProductDownload.product_id == product_id,
            models.ProductDownload.user_id == user_id,
        )
        .first()
    )

    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must purchase the product before reviewing it",
        )

    # Check for existing review
    existing_review = (
        db.query(models.ProductReview)
        .filter(
            models.ProductReview.product_id == product_id,
            models.ProductReview.user_id == user_id,
        )
        .first()
    )

    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this product",
        )

    # Create review
    db_review = models.ProductReview(
        product_id=product_id, user_id=user_id, **review.model_dump()
    )
    db.add(db_review)

    # Update product rating
    product = get_product(db, product_id)
    reviews = (
        db.query(models.ProductReview)
        .filter(models.ProductReview.product_id == product_id)
        .all()
    )
    product.rating = sum(r.rating for r in reviews) / len(reviews)

    db.commit()
    db.refresh(db_review)
    return db_review


def get_product_reviews(
    db: Session, product_id: int, skip: int = 0, limit: int = 10
) -> List[models.ProductReview]:
    """Get reviews for a product."""
    return (
        db.query(models.ProductReview)
        .filter(models.ProductReview.product_id == product_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def increment_product_view(db: Session, product_id: int):
    """Increment the view count for a product."""
    product = get_product(db, product_id)
    product.view_count += 1
    db.commit()


# Add browser extension specific validation and handling:
def validate_browser_extension(product: schemas.ProductCreate):
    """Validate browser extension specific fields"""
    if product.product_type == models.ProductType.BROWSER_EXTENSION:
        if not product.browser_support:
            raise HTTPException(
                status_code=400,
                detail="Browser support must be specified for browser extensions",
            )
        # Add more extension-specific validations


def create_product(db: Session, product: schemas.ProductCreate, developer_id: int):
    """Create a new marketplace product."""
    # Add browser extension validation
    if product.product_type == models.ProductType.BROWSER_EXTENSION:
        validate_browser_extension(product)

    # Your existing code...
    db_product = models.MarketplaceProduct(
        **product.model_dump(exclude={"video_ids"}),
        developer_id=developer_id,
    )
