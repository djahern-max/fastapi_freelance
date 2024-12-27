from pydantic_settings import BaseSettings
import os
from typing import Optional


class Settings(BaseSettings):
    env: str = "development"
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    # Remove local_video_upload_dir since we're using DO Spaces

    # Digital Ocean Spaces configuration
    spaces_name: str
    spaces_region: str
    spaces_endpoint: str
    spaces_bucket: str
    spaces_key: str
    spaces_secret: str

    class Config:
        env_file = os.getenv("ENV_FILE", ".env")
        extra = "ignore"


# Load settings
settings = Settings()
