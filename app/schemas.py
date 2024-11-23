from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List, ForwardRef
from enum import Enum
import enum


# ------------------ Enums ------------------
class UserType(str, enum.Enum):
    client = "client"
    developer = "developer"


class ConversationStatus(str, Enum):
    active = "active"
    negotiating = "negotiating"
    agreed = "agreed"
    completed = "completed"


# ------------------ User Schemas ------------------
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


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
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


class UserBasic(BaseModel):
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    id: int
    username: str


# ------------------ Profile Schemas ------------------
class DeveloperProfileCreate(BaseModel):
    skills: Optional[str] = None
    experience_years: Optional[int] = None
    hourly_rate: Optional[int] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    bio: Optional[str] = None


class ClientProfileCreate(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None


class DeveloperProfileUpdate(BaseModel):
    skills: Optional[str] = None
    experience_years: Optional[int] = None
    hourly_rate: Optional[int] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    bio: Optional[str] = None


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
    hourly_rate: Optional[int]
    github_url: Optional[str]
    portfolio_url: Optional[str]
    bio: Optional[str]
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
class VideoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    file_path: str
    thumbnail_path: Optional[str] = None
    is_project: bool = False
    parent_project_id: Optional[int] = None
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class VideoResponse(BaseModel):
    user_videos: List[VideoCreate]
    other_videos: List[VideoCreate]

    model_config = ConfigDict(from_attributes=True)


class VideoInfo(BaseModel):
    filename: str
    size: int
    last_modified: datetime
    url: str

    model_config = ConfigDict(from_attributes=True)


class SpacesVideoInfo(BaseModel):
    filename: str
    size: int
    last_modified: datetime
    url: str
    thumbnail_path: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ------------------ Project Schemas ------------------
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    pass


class ProjectOut(ProjectBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


# ------------------ Agreement Schemas ------------------
class NegotiationHistoryEntry(BaseModel):
    action: str
    user_id: int
    timestamp: datetime
    price: Optional[float] = None
    terms: Optional[str] = None
    changes: Optional[str] = None


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


class Agreement(AgreementBase):
    id: int
    status: str
    proposed_by: int
    proposed_at: datetime
    agreement_date: Optional[datetime]
    negotiation_history: List[dict]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgreementAccept(BaseModel):
    accepted_by: int
    accepted_at: datetime


# ------------------ Request Schemas ------------------
class RequestBase(BaseModel):
    title: str
    content: str
    project_id: Optional[int] = None
    is_public: bool = False
    estimated_budget: Optional[float] = None


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


class RequestCreate(RequestBase):
    pass


class RequestUpdate(RequestBase):
    pass


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
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    is_public: bool
    contains_sensitive_data: bool
    shared_with: Optional[List[SharedUserInfo]] = []
    current_agreement: Optional["Agreement"] = None
    current_proposal: Optional["Agreement"] = None

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
