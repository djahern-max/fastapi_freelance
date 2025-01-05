from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, HttpUrl
from typing import Optional, List, Dict, Any
from enum import Enum
import enum
import re
from datetime import datetime


# ------------------ Enums ------------------
class UserType(str, Enum):
    client = "client"
    developer = "developer"


class RequestStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class ConversationStatus(str, Enum):
    active = "active"
    negotiating = "negotiating"
    agreed = "agreed"
    completed = "completed"


class VideoType(str, Enum):
    project_overview = "project_overview"
    solution_demo = "solution_demo"
    progress_update = "progress_update"


class RequestPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RequestVisibility(str, Enum):
    private = "private"
    shared = "shared"
    public = "public"


class ProductType(str, Enum):
    BROWSER_EXTENSION = "browser_extension"
    WEB_APP = "web_app"
    API_SERVICE = "api_service"
    AUTOMATION_SCRIPT = "automation_script"


class PricingModel(str, Enum):
    ONE_TIME = "one_time"
    SUBSCRIPTION_MONTHLY = "subscription_monthly"
    SUBSCRIPTION_YEARLY = "subscription_yearly"
    USAGE_BASED = "usage_based"


# ------------------ User Schemas ------------------
class UserBase(BaseModel):
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class UserBasicInfo(UserBase):
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class UserBasic(BaseModel):
    id: int
    username: str

    class Config:
        from_orm = True


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    user_type: UserType
    terms_accepted: bool = Field(..., description="Must accept terms of agreement")

    @field_validator("user_type", mode="before")
    def user_type_to_lower(cls, v):
        return v.lower() if isinstance(v, str) else v

    @field_validator("terms_accepted")
    def terms_must_be_accepted(cls, v):
        if not v:
            raise ValueError("You must accept the terms of agreement to register.")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(UserBasicInfo):
    email: str
    is_active: bool
    user_type: UserType
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class User(BaseModel):
    id: int
    username: str
    is_active: bool
    user_type: UserType

    model_config = ConfigDict(from_attributes=True)


# Used for simple user references in other schemas
class UserBasic(UserBase):
    pass


# ------------------ Developer Rating ------------------


# Add these schemas for handling developer ratings
class DeveloperRatingBase(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class DeveloperRatingCreate(BaseModel):
    stars: int
    comment: Optional[str] = None


class DeveloperRatingUpdate(BaseModel):
    stars: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None


class DeveloperRatingOut(BaseModel):
    id: int
    developer_id: int
    user_id: int  # Changed from client_id
    stars: int
    comment: Optional[str] = None

    class Config:
        from_attributes = True


class DeveloperRatingStats(BaseModel):
    average_rating: float
    total_ratings: int
    rating_distribution: Dict[int, int]


class RatingResponse(BaseModel):
    success: bool
    average_rating: float
    total_ratings: int
    message: str


# ------------------ Profile Schemas ------------------
# First define the nested models
class SocialLink(BaseModel):
    platform: str
    url: str


class Achievement(BaseModel):
    title: str
    date: datetime
    description: Optional[str] = None
    url: Optional[str] = None


# Then modify the profile models to use Dict instead of the custom types for now
class DeveloperProfileCreate(BaseModel):
    skills: str
    experience_years: int = Field(ge=0)
    bio: Optional[str] = None
    is_public: bool = False


class ClientProfileCreate(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None


class DeveloperProfileUpdate(BaseModel):
    skills: Optional[str] = None
    experience_years: Optional[int] = Field(None, ge=0)
    bio: Optional[str] = None
    is_public: Optional[bool] = None
    profile_image_url: Optional[str] = None


class DeveloperProfilePublic(BaseModel):
    id: int
    user_id: int
    user: UserBasic  # Add this line to include user information
    skills: str
    experience_years: int
    bio: Optional[str] = None
    profile_image_url: Optional[str] = None
    rating: Optional[float] = Field(None, ge=0, le=5)
    total_projects: int
    success_rate: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientProfileUpdate(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None


class DeveloperProfileOut(BaseModel):
    id: int
    user_id: int
    skills: str
    experience_years: int
    bio: Optional[str] = None
    is_public: bool
    profile_image_url: Optional[str] = None
    rating: Optional[float] = None
    total_projects: int
    success_rate: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
    ratings: Optional[List[DeveloperRatingOut]] = None
    average_rating: Optional[float] = Field(None, ge=0, le=5)


class ClientProfileOut(BaseModel):
    id: int
    user_id: int
    company_name: Optional[str]
    industry: Optional[str]
    company_size: Optional[str]
    website: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ------------------ Token Schemas ------------------
class TokenData(BaseModel):
    id: Optional[int] = None


class Token(BaseModel):
    access_token: str
    token_type: str


# ------------------ Video Schemas ------------------


# Base schema with common fields
class VideoBase(BaseModel):
    title: str
    description: Optional[str] = None
    file_path: str
    thumbnail_path: Optional[str] = None
    project_id: Optional[int] = None
    request_id: Optional[int] = None
    video_type: VideoType = VideoType.solution_demo
    likes: int = 0
    liked_by_user: bool = False

    model_config = ConfigDict(from_attributes=True)


# Schema for creating videos
class VideoCreate(VideoBase):
    user_id: int


# Schema for updating videos
class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_path: Optional[str] = None
    project_id: Optional[int] = None
    request_id: Optional[int] = None
    video_type: Optional[VideoType] = None

    model_config = ConfigDict(from_attributes=True)


# Complete video information for responses
class VideoOut(VideoBase):
    id: int
    user_id: int
    upload_date: datetime


# Schema for returning lists of videos
class VideoResponse(BaseModel):
    user_videos: List[VideoOut]
    other_videos: List[VideoOut]

    model_config = ConfigDict(from_attributes=True)


# Schema for video with metadata from cloud storage
class SpacesVideoInfo(BaseModel):
    filename: str
    size: int
    last_modified: datetime
    url: str
    thumbnail_path: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    video_type: VideoType = VideoType.solution_demo
    project_id: Optional[int] = None
    request_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# Schema for video vote operations
class VideoVote(BaseModel):
    video_id: int
    dir: int  # 1 for like, 0 for unlike

    model_config = ConfigDict(from_attributes=True)


# Schema for video search/filter parameters
class VideoFilter(BaseModel):
    search: Optional[str] = None
    video_type: Optional[VideoType] = None
    user_id: Optional[int] = None
    project_id: Optional[int] = None
    request_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ------------------ Project Schemas ------------------


class UserPublicProfile(BaseModel):
    id: int
    username: str
    full_name: str
    profile_image_url: Optional[str]

    class Config:
        orm_mode = True


class ProjectBase(BaseModel):
    """Simplified project schema - just basic grouping info"""

    name: str
    description: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(ProjectBase):
    is_active: Optional[bool] = None


class ProjectStats(BaseModel):
    total: int
    open: int
    completed: int
    total_budget: float
    agreed_amount: float


class ConversationStats(BaseModel):
    total: int
    active: int
    negotiating: int
    agreed: int


class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]  # Make this optional if it can be null
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]  # Make this optional if it's nullable in the DB

    class Config:
        orm_mode = True


class ProjectWithRequests(ProjectOut):
    requests: List["RequestOut"] = []

    model_config = ConfigDict(from_attributes=True)


class ProjectTechnologyBase(BaseModel):
    name: str


class ProjectTechnologyCreate(ProjectTechnologyBase):
    pass


class ProjectTechnology(ProjectTechnologyBase):
    id: int
    project_id: int

    class Config:
        orm_mode = True


class ProjectPublish(BaseModel):
    is_public: bool = True
    live_url: Optional[str] = None
    repository_url: Optional[str] = None
    development_status: Optional[str] = None
    technologies: List[str] = []
    showcase_priority: Optional[int] = 0


class ProjectShowcase(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    live_url: Optional[str] = None
    repository_url: Optional[str] = None
    development_status: Optional[str] = None
    technologies: List[str] = []
    user: "UserPublicProfile"
    videos: List["VideoBase"]
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ------------------ Agreement Schemas ------------------


class AgreementBase(BaseModel):
    request_id: int
    price: float
    terms: str
    developer_id: int
    client_id: int
    proposed_changes: Optional[str] = None

    @field_validator("price")
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Price must be greater than 0")
        return v


class AgreementCreate(AgreementBase):
    pass


class NegotiationHistoryEntry(BaseModel):
    action: str  # 'proposal', 'acceptance', 'counter'
    user_id: int
    timestamp: datetime
    price: float
    terms: str
    changes: Optional[str] = None


class Agreement(AgreementBase):
    id: int
    status: str  # 'proposed', 'accepted', 'completed'
    proposed_by: int
    proposed_at: datetime
    agreement_date: Optional[datetime] = None
    negotiation_history: List[NegotiationHistoryEntry]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgreementAccept(BaseModel):
    accepted_by: int
    accepted_at: datetime


class AgreementStatus(BaseModel):
    request_id: int
    status: str


# ------------------ Request Schemas ------------------
class RequestBase(BaseModel):
    title: str
    content: str
    estimated_budget: Optional[float] = None
    is_public: bool = False
    contains_sensitive_data: bool = False


class RequestShareInfo(BaseModel):
    user_id: int
    username: str
    can_edit: bool

    model_config = ConfigDict(from_attributes=True)


class SimpleRequestOut(BaseModel):
    id: int
    title: str
    content: str
    project_id: Optional[int]
    user_id: int
    owner_username: str
    is_public: bool
    status: str
    estimated_budget: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    contains_sensitive_data: bool
    shared_with: List[RequestShareInfo] = Field(alias="shared_with_info")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RequestOut(BaseModel):
    id: int
    title: str
    content: str
    estimated_budget: Optional[float] = None
    is_public: bool
    contains_sensitive_data: bool
    user_id: int
    status: RequestStatus
    project_id: Optional[int] = None
    added_to_project_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    owner_username: str
    shared_with_info: List[dict] = []

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("owner_username", mode="before")
    @classmethod
    def get_owner_username(cls, v, values):
        if hasattr(v, "username"):
            return v.username
        return v


class RequestCreate(RequestBase):
    """Schema for creating a new request - project_id is optional"""

    project_id: Optional[int] = None
    developer_id: Optional[int] = None  # Add this field
    video_id: Optional[int] = None  # Add this field

    project_id: Optional[int] = None


class RequestUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    project_id: Optional[int] = None
    estimated_budget: Optional[float] = None
    is_public: Optional[bool] = None
    contains_sensitive_data: Optional[bool] = None
    status: Optional[RequestStatus] = None

    model_config = {
        "from_attributes": True,
        "use_enum_values": True,  # This ensures enum values are used directly
    }


class RequestInProject(BaseModel):
    """Schema for adding/removing a request to/from a project"""

    project_id: Optional[int] = None


class RequestShare(BaseModel):
    shared_with_user_id: int
    can_edit: bool

    model_config = ConfigDict(from_attributes=True)


class SharedUserInfo(BaseModel):
    user: UserBasic
    can_edit: bool

    model_config = ConfigDict(from_attributes=True)


class RequestShareResponse(BaseModel):
    id: int
    request_id: int
    shared_with_user_id: int
    can_edit: bool
    created_at: datetime
    viewed_at: Optional[datetime] = None
    is_new: bool = True  # Computed field

    model_config = ConfigDict(from_attributes=True)


class SharedRequestOut(BaseModel):
    id: int
    title: str
    content: str
    project_id: Optional[int]
    user_id: int
    owner_username: str
    is_public: bool
    status: str
    estimated_budget: Optional[float]
    created_at: datetime
    updated_at: Optional[datetime]
    contains_sensitive_data: bool
    shared_with_info: List[dict] = []
    is_new: bool
    share_id: int
    share_date: datetime  # Add this field

    model_config = ConfigDict(from_attributes=True)


class RequestShareWithUsername(BaseModel):
    id: int
    request_id: int
    shared_with_user_id: int
    can_edit: bool
    created_at: datetime
    username: str

    model_config = ConfigDict(from_attributes=True)


class PublicRequestOut(BaseModel):
    id: int
    title: str
    content: str
    user_id: int
    owner_username: str
    status: str
    estimated_budget: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class RequestProjectAction(BaseModel):
    """Track project grouping actions"""

    action: str  # "added_to_project" or "removed_from_project"
    project_id: Optional[int]
    timestamp: datetime


# ------------------ Response Schemas for Request-Centric Operations ------------------
class RequestActionResponse(BaseModel):
    """Generic response for request actions"""

    success: bool
    message: str
    request_id: int
    action: str  # e.g., "added_to_project", "removed_from_project", "status_updated"


class RequestWithDetails(RequestOut):
    """Extended request information including related data"""

    current_agreement: Optional["Agreement"] = None
    current_proposal: Optional["Agreement"] = None
    conversations: List["ConversationOut"] = []
    comments: List["RequestCommentResponse"] = []  # Changed from CommentOut
    project: Optional[ProjectBase] = (
        None  # Basic project info if request is in a project
    )

    model_config = ConfigDict(from_attributes=True)


# ------------------ Dashboard Schemas ------------------
class DashboardStats(BaseModel):
    """New schema for dashboard statistics"""

    total_requests: int
    open_requests: int
    in_progress_requests: int
    completed_requests: int
    total_projects: int
    active_projects: int


class RequestDashboard(BaseModel):
    """New schema for request-centric dashboard view"""

    recent_requests: List[RequestOut]
    active_conversations: List["ConversationOut"]
    shared_with_me: List["SharedRequestOut"]
    public_requests: List[RequestOut]

    model_config = ConfigDict(from_attributes=True)


# ------------------ Comment Schemas ------------------
class RequestCommentBase(BaseModel):
    content: str


class RequestCommentCreate(RequestCommentBase):
    request_id: int
    parent_id: Optional[int] = None


class RequestCommentVoteCreate(BaseModel):
    vote_type: int = Field(..., ge=-1, le=1)


class RequestCommentResponse(RequestCommentBase):
    id: int
    request_id: int
    user_id: int
    parent_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    user: UserBasic
    vote_count: int = 0
    user_vote: Optional[int] = None
    replies: List["RequestCommentResponse"] = []  # Using string literal

    model_config = ConfigDict(from_attributes=True)


# ------------------ Conversation Schemas ------------------
class ConversationCreate(BaseModel):
    request_id: int
    initial_message: Optional[str] = None
    video_ids: Optional[List[int]] = []
    include_profile: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)


class ConversationOut(BaseModel):
    id: int
    request_id: int
    starter_user_id: int
    recipient_user_id: int
    status: ConversationStatus
    agreed_amount: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageCreate(BaseModel):
    content: str
    video_ids: Optional[List[int]] = []
    include_profile: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)


class ConversationContentLink(BaseModel):
    id: int
    type: str  # 'video' or 'profile'
    content_id: int
    title: Optional[str] = None  # For videos
    url: Optional[str] = None  # For profile/video URLs

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageOut(BaseModel):
    id: int
    conversation_id: int
    user_id: int
    content: str
    created_at: datetime
    linked_content: List[ConversationContentLink] = []

    model_config = ConfigDict(from_attributes=True)


class ConversationWithMessages(BaseModel):
    id: int
    request_id: int
    starter_user_id: int
    recipient_user_id: int
    starter_username: str
    recipient_username: str
    status: ConversationStatus
    agreed_amount: Optional[int] = None
    created_at: datetime
    messages: List[ConversationMessageOut]
    request_title: str

    model_config = ConfigDict(from_attributes=True)


# Update forward references
RequestOut.model_rebuild()
RequestCommentResponse.model_rebuild()
ProjectWithRequests.model_rebuild()


class ConversationUpdate(BaseModel):
    status: str


class ConversationFromVideo(BaseModel):
    video_id: int
    title: str
    content: str
    user_id: int


# ------------------ Feedback Section ------------------


# In schemas.py
class FeedbackCreate(BaseModel):
    rating: int
    comment: str
    location: str
    target_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None

    @field_validator("rating")
    def rating_must_be_valid(cls, v):
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v

    @field_validator("email")
    def validate_email(cls, v):
        if v is not None and not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("Invalid email format")
        return v


class FeedbackResponse(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]
    rating: int
    comment: str
    location: str
    target_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ------------------ Subscription Section ------------------


class SubscriptionBase(BaseModel):
    stripe_subscription_id: str
    stripe_customer_id: str
    status: str
    current_period_end: datetime


class SubscriptionCreate(SubscriptionBase):
    user_id: int


class SubscriptionOut(SubscriptionBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class Vote(BaseModel):
    video_id: int
    dir: int = Field(..., description="1 to like, 0 to unlike")

    @field_validator("dir")
    def validate_direction(cls, v):
        if v not in [0, 1]:
            raise ValueError("Direction must be 0 or 1")
        return v

    model_config = ConfigDict(from_attributes=True)


# ------------------ Snagged Ticket ------------------


class SnaggedRequestOut(BaseModel):
    id: int
    request_id: int
    developer_id: int
    snagged_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class SnaggedRequestWithDetails(BaseModel):
    id: int
    request_id: int
    developer_id: int
    snagged_at: datetime
    is_active: bool
    request: dict = {
        "id": int,
        "title": str,
        "content": str,
        "status": str,
        "estimated_budget": Optional[float],
        "owner_username": str,
    }

    model_config = ConfigDict(from_attributes=True)


class SnaggedRequestCreate(BaseModel):
    request_id: int
    message: str
    profile_link: bool = False
    video_ids: List[int] = []

    model_config = ConfigDict(from_attributes=True)


# ------------------ AI Agent Marketplace ------------------


class ProductCategory(str, Enum):
    AUTOMATION = "automation"
    PROGRAMMING = "programming"
    MARKETING = "marketing"
    DATA_ANALYSIS = "data_analysis"
    CONTENT_CREATION = "content_creation"
    OTHER = "other"


class ProductStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class BrowserSupport(BaseModel):
    chrome: bool = True
    firefox: Optional[bool] = False
    safari: Optional[bool] = False
    edge: Optional[bool] = False


class ProductBase(BaseModel):
    name: str
    description: str
    long_description: Optional[str] = None
    price: float
    category: ProductCategory
    requirements: Optional[str] = None
    installation_guide: Optional[str] = None
    documentation_url: Optional[str] = None
    version: str = "1.0.0"
    # Add these new fields
    product_type: ProductType
    pricing_model: PricingModel = PricingModel.ONE_TIME
    browser_support: Optional[BrowserSupport] = None
    permissions_required: Optional[List[str]] = None
    manifest_version: Optional[str] = None

    @field_validator("permissions_required")
    def validate_permissions(cls, v):
        if v is None:
            return []
        valid_permissions = [
            "activeTab",
            "storage",
            "notifications",
            "webRequest",
            "scripting",
        ]
        for perm in v:
            if perm not in valid_permissions:
                raise ValueError(f"Invalid permission: {perm}")
        return v

    @field_validator("browser_support")
    def validate_browser_support(cls, v):
        if v is None:
            return BrowserSupport()
        return v


class ProductCreate(ProductBase):
    video_ids: Optional[List[int]] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    long_description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[ProductCategory] = None
    status: Optional[ProductStatus] = None
    version: Optional[str] = None
    requirements: Optional[str] = None
    installation_guide: Optional[str] = None
    documentation_url: Optional[str] = None
    video_ids: Optional[List[int]] = []


class ProductReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = None


class ProductReviewOut(BaseModel):
    id: int
    product_id: int
    user_id: int
    rating: int
    review_text: Optional[str]
    created_at: datetime
    user: UserBasic

    model_config = ConfigDict(from_attributes=True)


class ProductOut(ProductBase):
    id: int
    developer_id: int
    status: ProductStatus
    view_count: int
    download_count: int
    rating: Optional[float]
    created_at: datetime
    updated_at: Optional[datetime]
    developer: UserBasic
    reviews: List[ProductReviewOut] = []
    related_videos: List[VideoOut] = []

    model_config = ConfigDict(from_attributes=True)


class ProductDownloadOut(BaseModel):
    id: int
    product_id: int
    user_id: int
    price_paid: float
    transaction_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedProductResponse(BaseModel):
    items: List[ProductOut]
    total: int
    skip: int
    limit: int

    model_config = ConfigDict(from_attributes=True)
