from pydantic_settings import BaseSettings  # Import BaseSettings from pydantic-settings
from pydantic import ConfigDict  # Import ConfigDict from pydantic

class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    model_config = ConfigDict(env_file=".env")  # Configuration for the .env file

settings = Settings()



