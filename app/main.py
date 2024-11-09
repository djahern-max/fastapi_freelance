from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from app.routers import register, login, video_upload, display_videos, projects, command_notes, comments
from app.routers import request as requests_router  # Avoid naming conflict
from fastapi.routing import APIRoute

# Load environment variables
load_dotenv()

# Initialize FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)

# Retrieve allowed origins from the environment
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(register.router, prefix="/auth")
app.include_router(login.router, prefix="/auth")
app.include_router(projects.router)
app.include_router(video_upload.router)
app.include_router(display_videos.router)
app.include_router(requests_router.router)  # Use the renamed variable
app.include_router(comments.router)
app.include_router(command_notes.router)

# Debug route to check Spaces configuration
@app.get("/debug")
def debug_spaces():
    return {
        "SPACES_BUCKET": os.getenv("SPACES_BUCKET"),
        "SPACES_REGION": os.getenv("SPACES_REGION"),
        "SPACES_KEY": os.getenv("SPACES_KEY"),
        "SPACES_SECRET": os.getenv("SPACES_SECRET")
    }

# Simple test route
@app.get("/test")
def test():
    return {"message": "Server is running"}

# Route to get all available routes
@app.get("/routes")
async def get_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(
                {
                    "path": route.path,
                    "name": route.name,
                    "methods": route.methods
                }
            )
    return {"routes": routes}
