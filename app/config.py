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

    # Digital Ocean Spaces configuration
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

    class Config:
        env_file = os.getenv("ENV_FILE", ".env")
        extra = "ignore"


# Load settings
settings = Settings()
