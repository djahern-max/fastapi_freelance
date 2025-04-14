# Change this:
from app.utils import delete_from_spaces

# To this (assuming delete_from_spaces is in utils.py):
import sys
import os

# Get the parent directory of the current file
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the parent directory to sys.path if not already there
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Now you can import directly from the module
from utils import (
    delete_from_spaces,
    upload_to_spaces,
    get_file_from_storage,
    hash_password,
    verify_password,
)

# Re-export the functions
__all__ = [
    "delete_from_spaces",
    "upload_to_spaces",
    "get_file_from_storage",
    "hash_password",
    "verify_password",
]
