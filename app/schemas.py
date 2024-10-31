from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional, List


# ------------------ User Schemas ------------------

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str

class User(BaseModel):
    id: int
    username: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)  

class UserBasic(BaseModel):
    id: int
    username: str
    
    model_config = ConfigDict(from_attributes=True)

class UserBase(BaseModel):
    id: int
    username: str

# ------------------ Token Schemas ------------------

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    id: Optional[int] = None

# ------------------ Post and Vote Schemas ------------------

class PostBase(BaseModel):
    title: str
    content: str
    published: bool = True

class PostCreate(PostBase):
    pass

class PostResponse(PostBase):
    id: int
    created_at: datetime
    user_id: int
    owner: UserOut

    model_config = ConfigDict(from_attributes=True)

class Vote(BaseModel):
    post_id: int
    dir: int = Field(..., le=1)

    model_config = ConfigDict(from_attributes=True)

class Post(BaseModel):
    id: int
    created_at: datetime
    owner_id: int
    owner: UserOut

    model_config = ConfigDict(from_attributes=True)

class PostOut(BaseModel):
    id: int
    title: str
    content: str
    votes: int

    model_config = ConfigDict(from_attributes=True)

# ------------------ Email Schema ------------------

class EmailSchema(BaseModel):
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)

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

    class Config:
        orm_mode = True

class VideoInfo(BaseModel):
    filename: str
    size: int
    last_modified: datetime
    url: str

    class Config:
        orm_mode = True

class SpacesVideoInfo(BaseModel):
    filename: str
    size: int
    last_modified: datetime
    url: str
    thumbnail_path: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True

# ------------------ Note Schemas ------------------

class NoteBase(BaseModel):
    title: str
    content: str
    project_id: Optional[int]
    is_public: bool = False

class NoteShareInfo(BaseModel):
    user_id: int
    username: str
    can_edit: bool

    class Config:
        orm_mode = True

class SimpleNoteOut(BaseModel):
    id: int
    title: str
    content: str
    project_id: Optional[int]
    user_id: int
    owner_username: str  # Add this line
    is_public: bool
    created_at: datetime
    updated_at: Optional[datetime]
    contains_sensitive_data: bool
    shared_with: List[NoteShareInfo]

    class Config:
        orm_mode = True

class NoteCreate(NoteBase):
    pass

class NoteUpdate(NoteBase):
    pass

class NoteShare(BaseModel):
    shared_with_user_id: int
    can_edit: bool

    model_config = ConfigDict(from_attributes=True)

class NoteShareResponse(BaseModel):
    id: int
    note_id: int
    shared_with_user_id: int
    can_edit: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SharedUserInfo(BaseModel):
    user: UserBasic
    can_edit: bool

    model_config = ConfigDict(from_attributes=True)

class NoteOut(NoteBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]
    is_public: bool
    contains_sensitive_data: bool
    shared_with: Optional[List[SharedUserInfo]] = []

    model_config = ConfigDict(from_attributes=True)

class NoteShareWithUsername(BaseModel):
    id: int
    note_id: int
    shared_with_user_id: int
    can_edit: bool
    created_at: datetime
    username: str  # New field for username

    class Config:
        orm_mode = True

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
