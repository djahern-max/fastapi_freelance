# app/utils/storage.py
import boto3
import logging
import os
from botocore.exceptions import ClientError
import uuid

logger = logging.getLogger(__name__)

def get_s3_client():
    """Create and return an S3 client configured for Digital Ocean Spaces."""
    s3_client = boto3.client(
        "s3",
        region_name=os.getenv("SPACES_REGION"),
        endpoint_url=os.getenv("SPACES_ENDPOINT"),
        aws_access_key_id=os.getenv("SPACES_KEY"),
        aws_secret_access_key=os.getenv("SPACES_SECRET"),
    )
    return s3_client

def upload_file_to_spaces(file_content, filename, folder=""):
    """Upload a file to Digital Ocean Spaces."""
    s3_client = get_s3_client()
    
    # Generate a unique filename to avoid overwrites
    unique_filename = f"{uuid.uuid4()}-{filename}"
    
    # Combine folder and filename if folder is provided
    if folder:
        if not folder.endswith('/'):
            folder += '/'
        file_key = f"{folder}{unique_filename}"
    else:
        file_key = unique_filename
    
    try:
        # Get the bucket name from environment variables
        bucket_name = os.getenv("SPACES_BUCKET") or os.getenv("SPACES_NAME")
        
        # Log the configuration for debugging
        logger.debug(f"S3 Config - Bucket: {bucket_name}, Region: {os.getenv('SPACES_REGION')}")
        
        # Upload the file
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=file_content,
            ACL="public-read"  # Make the file publicly accessible
        )
        
        # Generate and return the URL
        file_url = f"{os.getenv('SPACES_ENDPOINT')}/{file_key}"
        logger.info(f"Successfully uploaded to Digital Ocean Spaces: {file_url}")
        return file_url
    except Exception as e:
        logger.error(f"Failed to upload file to Spaces: {e}")
        raise e

def delete_from_spaces(file_key):
    """Delete a file from Digital Ocean Spaces."""
    s3_client = get_s3_client()

    try:
        bucket_name = os.getenv("SPACES_BUCKET") or os.getenv("SPACES_NAME")
        s3_client.delete_object(Bucket=bucket_name, Key=file_key)
        logger.info(f"Successfully deleted file {file_key} from Spaces")
        return True
    except Exception as e:
        logger.error(f"Failed to delete file {file_key} from Spaces: {e}")
        raise e