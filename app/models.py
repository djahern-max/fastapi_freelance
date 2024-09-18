# models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(String, index=True)
    published = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    owner = relationship("User", back_populates="posts")
    votes = relationship("Vote", back_populates="post", cascade="all, delete")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    
    posts = relationship("Post", back_populates="owner", cascade="all, delete")
    votes = relationship("Vote", back_populates="user", cascade="all, delete")

class Vote(Base):
    __tablename__ = "votes"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    # value = Column(Integer, nullable=False)

    user = relationship("User", back_populates="votes")
    post = relationship("Post", back_populates="votes")

    __table_args__ = (
        UniqueConstraint('user_id', 'post_id', name='unique_vote'),
    )

class Newsletter(Base):
    __tablename__ = "newsletter"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)




















