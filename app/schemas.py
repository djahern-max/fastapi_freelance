from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from pydantic import ConfigDict
from typing import Optional
from typing import List

from pydantic import BaseModel

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

class Token(BaseModel):
    access_token: str
    token_type: str


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

    model_config = ConfigDict(from_attributes=True)  # Use ConfigDict for Pydantic v2.0

class Vote(BaseModel):
    post_id: int
    dir: int = Field(..., le=1)

    model_config = ConfigDict(from_attributes=True)  # Use ConfigDict for Pydantic v2.0

class Post(BaseModel):
    id: int
    created_at: datetime
    owner_id: int
    owner: UserOut

    model_config = ConfigDict(from_attributes=True)  # Replacing orm_mode with from_attributes

class PostOut(BaseModel):
    id: int
    title: str
    content: str
    votes: int

    model_config = ConfigDict(from_attributes=True)  # Use ConfigDict for Pydantic v2.0

class EmailSchema(BaseModel):
    email: EmailStr

class VideoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    file_path: str
    thumbnail_path: Optional[str] = None  # Add optional thumbnail path
    is_project: bool = False
    parent_project_id: Optional[int] = None
    user_id: int

    model_config = ConfigDict(from_attributes=True)

class VideoResponse(BaseModel):
    user_videos: List[VideoCreate]
    other_videos: List[VideoCreate]

    class Config:
        orm_mode = True  # Ensure ORM support if using SQLAlchemy models

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

    class Config:
        orm_mode = True

class TokenData(BaseModel):
    username: str = None
    id: int = None

    class Config:
        orm_mode = True  # Ensure ORM support if using SQLAlchemy models

class NoteBase(BaseModel):
    title: str
    content: str

class NoteCreate(NoteBase):
    pass

class NoteUpdate(NoteBase):
    pass

class NoteOut(NoteBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True