from pydantic_settings import BaseSettings
import os
from typing import Optional

class Settings(BaseSettings):
    env: str = 'development'  # Add this line
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    local_video_upload_dir: Optional[str] = None

    class Config:
        env_file = os.getenv('ENV_FILE', '.env')
        extra = 'ignore'  # Add this line to ignore extra fields

    # Digital Ocean Spaces configuration
    spaces_name: str = ''
    spaces_region: str = ''
    spaces_endpoint: str = ''
    spaces_bucket: str = ''
    spaces_key: str = ''
    spaces_secret: str = ''

# Load settings based on environment
settings = Settings()
