# app/utils/storage.py
import boto3
import logging
import os
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def delete_from_spaces(file_key):
    """Delete a file from Digital Ocean Spaces."""
    s3_client = boto3.client(
        "s3",
        region_name=os.getenv("SPACES_REGION"),
        endpoint_url=os.getenv("SPACES_ENDPOINT"),
        aws_access_key_id=os.getenv("SPACES_KEY"),
        aws_secret_access_key=os.getenv("SPACES_SECRET"),
    )

    try:
        bucket_name = os.getenv("SPACES_BUCKET") or os.getenv("SPACES_NAME")
        s3_client.delete_object(Bucket=bucket_name, Key=file_key)
        logger.info(f"Successfully deleted file {file_key} from Spaces")
        return True
    except Exception as e:
        logger.error(f"Failed to delete file {file_key} from Spaces: {e}")
        raise e
