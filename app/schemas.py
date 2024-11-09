from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

# ------------------ User Schemas ------------------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

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

class TokenData(BaseModel):
    id: Optional[int] = None  # Changed from user_id to id to match usage

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

# ------------------ Request Schemas (formerly Note Schemas) ------------------

class RequestBase(BaseModel):
    title: str
    content: str
    project_id: Optional[int]
    is_public: bool = False

class RequestShareInfo(BaseModel):
    user_id: int
    username: str
    can_edit: bool

    class Config:
        orm_mode = True

class SimpleRequestOut(BaseModel):
    id: int
    title: str
    content: str
    project_id: Optional[int]
    user_id: int
    owner_username: str
    is_public: bool
    created_at: datetime
    updated_at: Optional[datetime]
    contains_sensitive_data: bool
    shared_with: List[RequestShareInfo]

    class Config:
        orm_mode = True

class RequestCreate(RequestBase):
    pass

class RequestUpdate(RequestBase):
    pass

class RequestShare(BaseModel):
    shared_with_user_id: int
    can_edit: bool

    model_config = ConfigDict(from_attributes=True)

class RequestShareResponse(BaseModel):
    id: int
    request_id: int
    shared_with_user_id: int
    can_edit: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SharedUserInfo(BaseModel):
    user: UserBasic
    can_edit: bool

    model_config = ConfigDict(from_attributes=True)

class RequestOut(RequestBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]
    is_public: bool
    contains_sensitive_data: bool
    shared_with: Optional[List[SharedUserInfo]] = []

    model_config = ConfigDict(from_attributes=True)

class RequestShareWithUsername(BaseModel):
    id: int
    request_id: int
    shared_with_user_id: int
    can_edit: bool
    created_at: datetime
    username: str

    class Config:
        orm_mode = True

class PublicRequestOut(BaseModel):
    id: int
    title: str
    content: str
    user_id: int
    owner_username: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

# ------------------ Comment Schemas (formerly Note Comment) ------------------

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
    replies: List['RequestCommentResponse'] = []

    model_config = ConfigDict(from_attributes=True)

class RequestCommentCreate(BaseModel):
    content: str
    request_id: int
    parent_id: Optional[int] = None

# ------------------ CommandRequest Schemas (formerly CommandNote) ------------------

class CommandRequestBase(BaseModel):
    title: str
    description: Optional[str] = None
    commands: List[str]
    tags: List[str] = []

class CommandRequestCreate(CommandRequestBase):
    pass

class CommandRequestResponse(CommandRequestBase):
    id: int
    user_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class CommandExecutionResult(BaseModel):
    command: str
    success: bool
    output: str
    executed_at: datetime

class CommandExecutionResponse(BaseModel):
    request_id: int
    title: str
    results: List[CommandExecutionResult]
    
    model_config = ConfigDict(from_attributes=True)

class CommandNoteResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: str
    commands: List[str]
    tags: List[str]
    created_at: datetime

class CommandNoteCreate(BaseModel):
    title: str
    description: Optional[str] = None
    commands: List[str]
    tags: Optional[List[str]] = []
