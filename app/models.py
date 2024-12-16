from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Enum as SQLAlchemyEnum,
    TIMESTAMP,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Float,
    JSON,
    text,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
import enum
from datetime import datetime
from .database import Base


# ------------------ Mixin ------------------
class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())


# ------------------ Enums ------------------
class UserType(str, enum.Enum):
    client = "client"
    developer = "developer"


class RequestStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class ConversationStatus(str, enum.Enum):
    active = "active"
    negotiating = "negotiating"
    agreed = "agreed"
    completed = "completed"


class VideoType(str, enum.Enum):
    project_overview = "project_overview"
    solution_demo = "solution_demo"
    progress_update = "progress_update"


# ------------------ User Model ------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    user_type = Column(SQLAlchemyEnum(UserType), nullable=False)
    terms_accepted = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    stripe_customer_id = Column(String, nullable=True)

    # Relationships
    videos = relationship("Video", back_populates="user", cascade="all, delete-orphan")
    requests = relationship("Request", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    shared_requests = relationship(
        "RequestShare",
        foreign_keys="[RequestShare.shared_with_user_id]",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    request_comments = relationship(
        "RequestComment", back_populates="user", cascade="all, delete-orphan"
    )
    developer_profile = relationship(
        "DeveloperProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    client_profile = relationship(
        "ClientProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    subscription = relationship(
        "Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


# ------------------ Profile Models ------------------
class DeveloperProfile(Base):
    __tablename__ = "developer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    skills = Column(String)
    experience_years = Column(Integer)
    bio = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Profile visibility and display
    is_public = Column(Boolean, default=False)
    profile_image_url = Column(String, nullable=True)

    # Success metrics
    rating = Column(Float, nullable=True)  # Average rating from clients
    total_projects = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)  # Percentage of successful projects

    # Relationship
    user = relationship("User", back_populates="developer_profile")

    ratings = relationship("DeveloperRating", back_populates="developer")


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    company_name = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    website = Column(String, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="client_profile")


# ------------------ Video Model ------------------
class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    thumbnail_path = Column(String, nullable=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    video_type = Column(SQLAlchemyEnum(VideoType), nullable=False, default=VideoType.solution_demo)

    # Relationships
    user = relationship("User", back_populates="videos")
    project = relationship("Project", back_populates="videos")
    request = relationship("Request", back_populates="videos")
    votes = relationship(
        "Vote", back_populates="video", cascade="all, delete-orphan"
    )  # Add this line


# ------------------ Project Model ------------------
class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Project metadata
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="projects")
    requests = relationship("Request", back_populates="project")
    videos = relationship("Video", back_populates="project")


# ------------------ Request and RequestShare Models ------------------
class Request(Base, TimestampMixin):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(SQLAlchemyEnum(RequestStatus), default=RequestStatus.open, nullable=False)

    # Optional project grouping
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    added_to_project_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Visibility and sharing
    is_public = Column(Boolean, default=False)
    contains_sensitive_data = Column(Boolean, default=False)

    # Business details
    estimated_budget = Column(Float, nullable=True)
    agreed_amount = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="requests")
    project = relationship("Project", back_populates="requests")
    shared_with = relationship(
        "RequestShare", back_populates="request", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "Conversation", back_populates="request", cascade="all, delete-orphan"
    )
    comments = relationship(
        "RequestComment", back_populates="request", cascade="all, delete-orphan"
    )
    agreements = relationship("Agreement", back_populates="request", cascade="all, delete-orphan")
    videos = relationship("Video", back_populates="request")

    # Methods to handle agreement states
    def get_current_agreement(self):
        return next((a for a in self.agreements if a.status == "active"), None)

    def get_current_proposal(self):
        return next((a for a in self.agreements if a.status == "proposed"), None)


class RequestShare(Base):
    __tablename__ = "request_shares"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
    shared_with_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    can_edit = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    viewed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    request = relationship("Request", back_populates="shared_with")
    user = relationship("User", foreign_keys=[shared_with_user_id])

    __table_args__ = (
        UniqueConstraint("request_id", "shared_with_user_id", name="unique_request_share"),
    )


# ------------------ Comment Models ------------------
class RequestComment(Base):
    __tablename__ = "request_comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(
        Integer, ForeignKey("request_comments.id", ondelete="CASCADE"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    request = relationship("Request", back_populates="comments")
    user = relationship("User", back_populates="request_comments")
    replies = relationship("RequestComment", backref=backref("parent", remote_side=[id]))
    votes = relationship("RequestCommentVote", back_populates="comment", cascade="all, delete")


class RequestCommentVote(Base):
    __tablename__ = "request_comment_votes"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    comment_id = Column(
        Integer, ForeignKey("request_comments.id", ondelete="CASCADE"), primary_key=True
    )
    vote_type = Column(Integer, nullable=False)  # 1 for upvote, -1 for downvote
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    comment = relationship("RequestComment", back_populates="votes")

    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="unique_request_comment_vote"),
    )


# ------------------ Conversation Models ------------------
class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    starter_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(
        SQLAlchemyEnum(ConversationStatus), nullable=False, default=ConversationStatus.active
    )

    # Relationships
    request = relationship("Request", back_populates="conversations")
    starter = relationship("User", foreign_keys=[starter_user_id])
    recipient = relationship("User", foreign_keys=[recipient_user_id])
    messages = relationship(
        "ConversationMessage", back_populates="conversation", cascade="all, delete-orphan"
    )
    content_links = relationship(
        "ConversationContentLink", back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User")
    content_links = relationship(
        "ConversationContentLink", back_populates="message", cascade="all, delete-orphan"
    )


class ConversationContentLink(Base):
    __tablename__ = "conversation_content_links"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_id = Column(
        Integer, ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False
    )
    content_type = Column(String, nullable=False)  # 'video' or 'profile'
    content_id = Column(Integer, nullable=False)  # video_id or user_id
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="content_links")
    message = relationship("ConversationMessage", back_populates="content_links")

    __table_args__ = (
        UniqueConstraint("message_id", "content_type", "content_id", name="unique_content_link"),
    )


# ------------------ Agreement Model ------------------


class Agreement(Base, TimestampMixin):
    __tablename__ = "agreements"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
    developer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    price = Column(Float, nullable=False)
    terms = Column(Text, nullable=False)
    status = Column(String, nullable=False)  # 'proposed', 'accepted', 'completed'
    proposed_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    proposed_changes = Column(Text, nullable=True)
    negotiation_history = Column(JSON, nullable=False, default=list)
    # Add these two fields
    proposed_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    agreement_date = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships remain the same
    request = relationship("Request", back_populates="agreements")
    developer = relationship("User", foreign_keys=[developer_id])
    client = relationship("User", foreign_keys=[client_id])
    proposer = relationship("User", foreign_keys=[proposed_by])


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)  # Optional name for anonymous users
    email = Column(String, nullable=True)  # Optional email for anonymous users
    rating = Column(Integer)
    comment = Column(String)
    location = Column(String)  # Where in the app the feedback was given
    target_id = Column(String, nullable=True)  # ID of the specific item being rated
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ------------------ Subscription Model ------------------


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stripe_subscription_id = Column(String, unique=True, nullable=False)
    stripe_customer_id = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False)  # active, canceled, past_due
    current_period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Add to User model
    user = relationship("User", back_populates="subscription")


class Vote(Base):
    __tablename__ = "votes"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")
    video = relationship("Video", back_populates="votes")


# ------------------ Developer Rating System ------------------


class DeveloperRating(Base):
    __tablename__ = "developer_ratings"

    id = Column(Integer, primary_key=True, nullable=False)
    developer_id = Column(
        Integer, ForeignKey("developer_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stars = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())

    # Relationships
    developer = relationship("DeveloperProfile", back_populates="ratings")
    user = relationship("User")  # Change this from "client" to "user"

    __table_args__ = (
        # Ensure a user can only rate a developer once
        UniqueConstraint("developer_id", "user_id", name="unique_developer_user_rating"),
        # Ensure rating is between 1 and 5
        CheckConstraint("stars >= 1 AND stars <= 5", name="stars_range_check"),
    )


# ------------------ Snagged Ticke Model ------------------


class SnaggedRequest(Base):
    __tablename__ = "snagged_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
    developer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    snagged_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True)  # For soft delete/hide functionality

    # Relationships
    request = relationship("Request", backref="snagged_by")
    developer = relationship("User", backref="snagged_requests")

    __table_args__ = (
        UniqueConstraint("request_id", "developer_id", name="unique_snagged_request"),
    )
