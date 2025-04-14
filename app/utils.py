import bcrypt
import boto3
import logging
from botocore.config import Config
from botocore.exceptions import ClientError
from .config import settings
import io

# Set up logger
logger = logging.getLogger(__name__)


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
        raise


def delete_from_spaces(file_key):
    """Delete a file from Digital Ocean Spaces."""
    s3_client = boto3.client(
        "s3",
        region_name=settings.spaces_region,
        endpoint_url=settings.spaces_endpoint,
        aws_access_key_id=settings.spaces_key,
        aws_secret_access_key=settings.spaces_secret,
    )

    try:
        # Make sure spaces_name and spaces_bucket are consistent
        bucket_name = settings.spaces_bucket or settings.spaces_name
        s3_client.delete_object(Bucket=bucket_name, Key=file_key)
        logger.info(f"Successfully deleted file {file_key} from Spaces")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete file {file_key} from Spaces: {e}")
        raise e


def upload_to_spaces(file_path: str, destination_key: str) -> str:
    """Upload a file to Digital Ocean Spaces from a local path."""
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

        # Make sure spaces_name and spaces_bucket are consistent
        bucket_name = settings.spaces_bucket or settings.spaces_name

        # Upload the file
        client.upload_file(
            file_path, bucket_name, destination_key, ExtraArgs={"ACL": "public-read"}
        )

        # Return the public URL
        return f"https://{bucket_name}.{settings.spaces_region}.digitaloceanspaces.com/{destination_key}"
    except Exception as e:
        logger.error(f"Failed to upload file to Spaces: {e}")
        raise e
