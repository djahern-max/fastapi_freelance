import requests
from fastapi import APIRouter

router = APIRouter()

YOUTUBE_API_KEY = ""
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

@router.get("/videos")
def get_ai_videos():
    params = {
        "part": "snippet",
        "q": "AI technology",
        "type": "video",
        "key": YOUTUBE_API_KEY,
        "maxResults": 10
    }
    response = requests.get(YOUTUBE_SEARCH_URL, params=params)
    return response.json()
