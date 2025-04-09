from pydantic_settings import BaseSettings
import os
from typing import Optional
import tempfile


# TEST PUSH
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
    google_client_id: str
    google_client_secret: str
    google_oauth_redirect_url: str
    github_client_id: str
    github_client_secret: str
    github_oauth_redirect_url: str
    linkedin_client_id: Optional[str] = None
    linkedin_client_secret: Optional[str] = None
    linkedin_oauth_redirect_url: Optional[str] = None
    session_secret: str
    EXTERNAL_API_KEY: str

    spaces_name: str
    spaces_region: str
    spaces_endpoint: str
    spaces_bucket: str
    spaces_key: str
    spaces_secret: str
    # Add Stripe configuration
    stripe_secret_key: str
    stripe_public_key: str
    stripe_webhook_secret: str
    stripe_price_id: str
    frontend_url: str
    # Add local video upload directory with a temporary directory
    local_video_upload_dir: Optional[str] = tempfile.gettempdir()
    # Add Analytics Hub API URL
    ANALYTICS_HUB_API_URL: Optional[str] = None

    class Config:
        env_file = os.getenv("ENV_FILE", ".env")
        extra = "ignore"


# Load settings
settings = Settings()
