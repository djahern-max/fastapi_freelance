import boto3
import os
from botocore.client import Config

# Digital Ocean Spaces configuration
endpoint_url = 'https://nyc3.digitaloceanspaces.com'
access_key = 'DO00P4DXX6A88URVKEAU'
secret_key = 'vrEqN3UasSoJhrGc6eVtdMwG1Y2myGCkdoh+gE7hBJI'
bucket_name = 'ryzevideosv3'
file_name = '7b0f8b9f-c2c0-47c8-ac51-7371526ba5c0.webp'
local_file_path = r'C:\Users\dahern\Documents\RYZE.AI\fastapi\scripts\downloaded_thumbnail.webp'

# Create a session using DigitalOcean Spaces credentials
session = boto3.session.Session()

# Create S3 client
s3_client = session.client('s3',
                           region_name='your-region',
                           endpoint_url=endpoint_url,
                           aws_access_key_id=access_key,
                           aws_secret_access_key=secret_key,
                           config=Config(signature_version='s3v4'))

# Download the file
try:
    s3_client.download_file(bucket_name, file_name, local_file_path)
    print(f"File downloaded successfully to {local_file_path}")
except Exception as e:
    print(f"An error occurred: {str(e)}")