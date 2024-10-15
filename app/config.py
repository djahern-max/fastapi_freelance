from pydantic import BaseSettings
import os
from typing import Optional

class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    spaces_token: str
    spaces_name: str
    spaces_region: str
    spaces_endpoint: str
    spaces_bucket: str
    local_video_upload_dir: Optional[str] = None

    class Config:
        env_file = os.getenv('ENV_FILE', '.env')

# Load settings based on environment
settings = Settings()

