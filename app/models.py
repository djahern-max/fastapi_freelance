from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

# Single User Model Definition
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    posts = relationship("Post", back_populates="owner", cascade="all, delete")
    votes = relationship("Vote", back_populates="user", cascade="all, delete")
    videos = relationship("Video", back_populates="user")
    notes = relationship("Note", back_populates="user")


class Post(Base, TimestampMixin):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(String, index=True)
    published = Column(Boolean, default=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="posts")
    votes = relationship("Vote", back_populates="post", cascade="all, delete")


class Vote(Base):
    __tablename__ = "votes"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="votes")
    post = relationship("Post", back_populates="votes")

    __table_args__ = (
        UniqueConstraint('user_id', 'post_id', name='unique_vote'),
    )


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    is_project = Column(Boolean, default=False)
    parent_project_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="videos")


class Newsletter(Base):
    __tablename__ = "newsletter"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="notes")








