from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, UniqueConstraint, DateTime, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from pydantic import BaseModel, ConfigDict
from typing import Optional
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY

# ------------------ Mixin ------------------

class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

# ------------------ User Model ------------------

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
    projects = relationship("Project", back_populates="user")
    shared_notes = relationship("NoteShare", foreign_keys="[NoteShare.shared_with_user_id]", back_populates="user")
    command_notes = relationship("CommandNote", back_populates="owner", cascade="all, delete")  # Add this line
# ------------------ Post and Vote Models ------------------

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

# ------------------ Video Model ------------------

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    thumbnail_path = Column(String, nullable=True)  # Thumbnail path column
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    is_project = Column(Boolean, default=False)
    parent_project_id = Column(Integer, ForeignKey("videos.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="videos")

# ------------------ Video Pydantic Model ------------------

class VideoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    file_path: str
    is_project: bool = False
    parent_project_id: Optional[int] = None
    user_id: int

    model_config = ConfigDict(from_attributes=True)

# ------------------ Newsletter Model ------------------

class Newsletter(Base):
    __tablename__ = "newsletter"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    model_config = ConfigDict(from_attributes=True)

# ------------------ Note and NoteShare Models ------------------

class Note(Base):
    __tablename__ = "notes"
    
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
    user = relationship("User", back_populates="notes")
    project = relationship("Project", back_populates="notes")
    shared_with = relationship("NoteShare", back_populates="note", cascade="all, delete")

class NoteShare(Base):
    __tablename__ = "note_shares"
    
    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    shared_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    can_edit = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    note = relationship("Note", back_populates="shared_with")
    user = relationship("User", foreign_keys=[shared_with_user_id], back_populates="shared_notes")

    __table_args__ = (
        UniqueConstraint('note_id', 'shared_with_user_id', name='unique_note_share'),
    )

# ------------------ Project Model ------------------

class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    user = relationship("User", back_populates="projects")
    notes = relationship("Note", back_populates="project")

# ------------------ Command Models ------------------

class CommandNote(Base):
    __tablename__ = "command_notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    commands = Column(PG_ARRAY(String), nullable=False)  # Use PostgreSQL ARRAY
    tags = Column(PG_ARRAY(String), nullable=True)       # Use PostgreSQL ARRAY
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner = relationship("User", back_populates="command_notes")