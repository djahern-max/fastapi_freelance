import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError

# Load .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Load environment variables
SPACES_NAME = os.getenv('SPACES_NAME')
SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT = os.getenv('SPACES_ENDPOINT')
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_KEY = os.getenv('SPACES_KEY')
SPACES_SECRET = os.getenv('SPACES_SECRET')

# Initialize the boto3 client
s3 = boto3.client('s3',
                  region_name=SPACES_REGION,
                  endpoint_url=SPACES_ENDPOINT,
                  aws_access_key_id=SPACES_KEY,
                  aws_secret_access_key=SPACES_SECRET)

def upload_to_spaces(local_file, spaces_file):
    try:
        s3.upload_file(local_file, SPACES_BUCKET, spaces_file)
        print(f"Upload Successful: {spaces_file}")
        return True
    except FileNotFoundError:
        print("The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return False

# Test the upload
local_file_path = r"C:\Users\dahern\Documents\RYZE.AI\fastapi\videos\test_video.mp4"
spaces_file_name = "test_upload.mp4"

if not os.path.exists(local_file_path):
    print(f"Error: The file {local_file_path} does not exist.")
else:
    success = upload_to_spaces(local_file_path, spaces_file_name)

    if success:
        print(f"File uploaded successfully. URL: https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{spaces_file_name}")
    else:
        print("Upload failed.")

# Print out environment variables for debugging (be careful not to expose sensitive information)
print(f"SPACES_NAME: {SPACES_NAME}")
print(f"SPACES_REGION: {SPACES_REGION}")
print(f"SPACES_ENDPOINT: {SPACES_ENDPOINT}")
print(f"SPACES_BUCKET: {SPACES_BUCKET}")
print(f"SPACES_KEY: {'Set' if SPACES_KEY else 'Not set'}")
print(f"SPACES_SECRET: {'Set' if SPACES_SECRET else 'Not set'}")