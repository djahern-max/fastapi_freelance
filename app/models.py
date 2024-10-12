from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class TimestampMixin:
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    posts = relationship("Post", back_populates="owner", cascade="all, delete")  # Ensure this exists
    votes = relationship("Vote", back_populates="user", cascade="all, delete")
    videos = relationship("Video", back_populates="user")

class Post(Base, TimestampMixin):
    __tablename__ = "posts"  # Changed back to "posts" to match existing table
    title = Column(String, index=True)
    content = Column(String, index=True)
    published = Column(Boolean, default=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    owner = relationship("User", back_populates="posts")
    votes = relationship("Vote", back_populates="post", cascade="all, delete")

class Vote(Base):
    __tablename__ = "votes"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    user = relationship("User", back_populates="votes")
    post = relationship("Post", back_populates="votes")
    __table_args__ = (
        UniqueConstraint('user_id', 'post_id', name='unique_vote'),
    )

     # Relationship with User
    user = relationship("User", back_populates="votes")
    
    # Relationship with Post
    post = relationship("Post", back_populates="votes")

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    is_project = Column(Boolean, default=False)
    parent_project_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Add this line

    user = relationship("User", back_populates="videos")  # Add this line if you want to set up a relationship

class Newsletter(Base):
    __tablename__ = "newsletter"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)












