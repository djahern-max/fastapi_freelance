from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database settings
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str

    # Security settings
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    # Environment settings
    env: str  # "local" or "production"
    local_video_upload_dir: str  # Path for local storage
    spaces_token: str  # DigitalOcean Spaces token
    spaces_name: str  # Name of your Space
    spaces_region: str  # Region of your Space (e.g., nyc3)
    spaces_endpoint: str  # DigitalOcean Spaces endpoint URL
    spaces_bucket: str  # Bucket name in DigitalOcean Spaces

    # Configuration for loading environment variables from .env
    model_config = SettingsConfigDict(env_file=".env")

# Instantiate settings
settings = Settings()
