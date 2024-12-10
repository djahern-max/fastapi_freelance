from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, HttpUrl
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import enum
import re


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

    @field_validator("user_type", mode="before")
    def user_type_to_lower(cls, v):
        return v.lower() if isinstance(v, str) else v


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


# Add VideoType enum
class VideoType(str, Enum):
    project_overview = "project_overview"
    solution_demo = "solution_demo"
    progress_update = "progress_update"


# Update VideoCreate schema
class VideoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    file_path: str
    thumbnail_path: Optional[str] = None
    project_id: Optional[int] = None
    request_id: Optional[int] = None
    video_type: VideoType = VideoType.solution_demo
    user_id: int

    model_config = ConfigDict(from_attributes=True)


# Update VideoResponse schema to use updated VideoCreate
class VideoResponse(BaseModel):
    user_videos: List[VideoCreate]
    other_videos: List[VideoCreate]

    model_config = ConfigDict(from_attributes=True)


# Add new VideoOut schema for complete video information
class VideoOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    file_path: str
    thumbnail_path: Optional[str]
    upload_date: datetime
    project_id: Optional[int]
    request_id: Optional[int]
    user_id: int
    video_type: VideoType

    model_config = ConfigDict(from_attributes=True)


# Update SpacesVideoInfo schema
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


# ------------------ Project Schemas ------------------
class ProjectBase(BaseModel):
    """Simplified project schema - just basic grouping info"""

    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


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


class ProjectOut(ProjectBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    request_stats: ProjectStats
    conversation_stats: ConversationStats
    last_activity: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectWithRequests(ProjectOut):
    requests: List["RequestOut"] = []

    model_config = ConfigDict(from_attributes=True)


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


class RequestCreate(RequestBase):
    """Schema for creating a new request - project_id is optional"""

    project_id: Optional[int] = None


class RequestUpdate(BaseModel):
    """Schema for updating a request - all fields optional"""

    title: Optional[str] = None
    content: Optional[str] = None
    project_id: Optional[int] = None
    estimated_budget: Optional[float] = None
    is_public: Optional[bool] = None
    contains_sensitive_data: Optional[bool] = None


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


class RequestOut(RequestBase):
    id: int
    user_id: int
    status: RequestStatus
    project_id: Optional[int] = None
    added_to_project_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    owner_username: str
    shared_with_info: List[dict] = []

    class Config:
        from_attributes = True
        populate_by_name = True

    @field_validator("owner_username", mode="before")
    @classmethod
    def get_owner_username(cls, v, values):
        if hasattr(v, "username"):
            return v.username
        return v


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
    project: Optional[ProjectBase] = None  # Basic project info if request is in a project

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

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageOut(BaseModel):
    id: int
    conversation_id: int
    user_id: int
    content: str
    created_at: datetime

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
