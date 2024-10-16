import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Spaces configuration from environment variables
SPACES_NAME = os.getenv('SPACES_NAME')
SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT = os.getenv('SPACES_ENDPOINT')
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_KEY = os.getenv('SPACES_KEY')
SPACES_SECRET = os.getenv('SPACES_SECRET')

print(f"Accessing bucket: {SPACES_BUCKET}")
print(f"Using endpoint: {SPACES_ENDPOINT}")

# Initialize the boto3 client for S3
s3 = boto3.client('s3',
                  region_name=SPACES_REGION,
                  endpoint_url=SPACES_ENDPOINT,
                  aws_access_key_id=SPACES_KEY,
                  aws_secret_access_key=SPACES_SECRET)

def list_files():
    """List all files in the specified Spaces bucket."""
    try:
        response = s3.list_objects_v2(Bucket=SPACES_BUCKET)
        if 'Contents' in response:
            for item in response['Contents']:
                print(f"File: {item['Key']}, Size: {item['Size']} bytes, Last Modified: {item['LastModified']}")
        else:
            print("No files found in the bucket.")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"ClientError: {error_code} - {error_message}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

def get_file_url(file_name):
    """Get the public URL for a file in the bucket."""
    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{file_name}"

def main():
    """Main function to list files and generate URLs."""
    print("\nListing files in the specified bucket:")
    list_files()
    
    file_name = input("\nEnter the name of a file to get its URL (or press Enter to skip): ")
    if file_name:
        url = get_file_url(file_name)
        print(f"URL for {file_name}: {url}")

if __name__ == "__main__":
    main()
