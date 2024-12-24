import bcrypt
import boto3
from botocore.config import Config
from .config import settings
import io


# Existing password functions
def hash_password(password: str) -> str:
    """Hashes a plain text password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies that a plain text password matches the hashed password."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


# New storage function
async def get_file_from_storage(file_path: str) -> io.BytesIO:
    """
    Retrieves a file from Digital Ocean Spaces storage.
    Uses the same DO Spaces connection as video upload.
    """
    try:
        # Configure DO Spaces client
        session = boto3.session.Session()
        client = session.client(
            "s3",
            endpoint_url=settings.spaces_endpoint,
            config=Config(signature_version="s3v4"),
            region_name=settings.spaces_region,
            aws_access_key_id=settings.spaces_key,
            aws_secret_access_key=settings.spaces_secret,
        )

        # Get the file from spaces
        response = client.get_object(
            Bucket=settings.spaces_name,  # Changed to match your env variable
            Key=file_path,
        )

        # Create a BytesIO object from the file data
        file_data = io.BytesIO(response["Body"].read())
        file_data.seek(0)

        return file_data

    except Exception as e:
        print(f"Error retrieving file from storage: {str(e)}")
        raise
