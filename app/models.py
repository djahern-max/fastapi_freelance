from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import backref

# ------------------ Mixin ------------------

class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

# ------------------ User Model ------------------
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships remain the same
    videos = relationship("Video", back_populates="user")
    requests = relationship("Request", back_populates="user")
    projects = relationship("Project", back_populates="user")
    shared_requests = relationship("RequestShare", foreign_keys="[RequestShare.shared_with_user_id]", back_populates="user")
    command_requests = relationship("CommandRequest", back_populates="owner")
    request_comments = relationship("RequestComment", back_populates="user")

# ------------------ Video Model ------------------

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    thumbnail_path = Column(String, nullable=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    is_project = Column(Boolean, default=False)
    parent_project_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="videos")

# ------------------ Project Model ------------------

class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    user = relationship("User", back_populates="projects")
    requests = relationship("Request", back_populates="project")

# ------------------ Request and RequestShare Models ------------------

class Request(Base):
    __tablename__ = "requests"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    is_public = Column(Boolean, default=False)
    contains_sensitive_data = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="requests")
    project = relationship("Project", back_populates="requests")
    shared_with = relationship("RequestShare", back_populates="request", cascade="all, delete")
    comments = relationship("RequestComment", back_populates="request", cascade="all, delete")

class RequestShare(Base):
    __tablename__ = "request_shares"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
    shared_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    can_edit = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    request = relationship("Request", back_populates="shared_with")
    user = relationship("User", foreign_keys=[shared_with_user_id], back_populates="shared_requests")

    __table_args__ = (
        UniqueConstraint('request_id', 'shared_with_user_id', name='unique_request_share'),
    )

# ------------------ Comment Model ------------------

class RequestComment(Base):
    __tablename__ = "request_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("request_comments.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    request = relationship("Request", back_populates="comments")
    user = relationship("User", back_populates="request_comments")
    replies = relationship("RequestComment", backref=backref("parent", remote_side=[id]))
    votes = relationship("RequestCommentVote", back_populates="comment", cascade="all, delete")

class RequestCommentVote(Base):
    __tablename__ = "request_comment_votes"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    comment_id = Column(Integer, ForeignKey("request_comments.id", ondelete="CASCADE"), primary_key=True)
    vote_type = Column(Integer, nullable=False)  # 1 for upvote, -1 for downvote
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")
    comment = relationship("RequestComment", back_populates="votes")

    __table_args__ = (
        UniqueConstraint('user_id', 'comment_id', name='unique_request_comment_vote'),
    )

# ------------------ CommandRequest Model ------------------

class CommandRequest(Base):
    __tablename__ = "command_requests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    commands = Column(PG_ARRAY(String), nullable=False)
    tags = Column(PG_ARRAY(String), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="command_requests")
