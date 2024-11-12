from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from app.routers import register, login, video_upload, display_videos, projects, comments, conversations, profile
from app.routers import request as requests_router
from fastapi.routing import APIRoute
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log all routes at startup
    logger.info("Available routes:")
    for route in app.routes:
        if isinstance(route, APIRoute):
            logger.info(f"{', '.join(route.methods)} {route.path}")
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

# Function to print routes from a router
def log_router_routes(router, prefix=""):
    for route in router.routes:
        if isinstance(route, APIRoute):
            logger.info(f"{', '.join(route.methods)} {prefix}{route.path}")

# Register routers and log their routes
routers_with_prefixes = [
    (register.router, "/auth"),
    (login.router, "/auth"),
    (projects.router, ""),
    (video_upload.router, ""),
    (display_videos.router, ""),
    (requests_router.router, ""),
    (comments.router, ""),
    (conversations.router, ""),
    (profile.router, "")
]

for router, prefix in routers_with_prefixes:
    app.include_router(router, prefix=prefix)
    logger.info(f"\nRoutes for {router.__class__.__name__}:")
    log_router_routes(router, prefix)

@app.get("/debug")
def debug_spaces():
    return {
        "SPACES_BUCKET": os.getenv("SPACES_BUCKET"),
        "SPACES_REGION": os.getenv("SPACES_REGION"),
        "SPACES_KEY": os.getenv("SPACES_KEY"),
        "SPACES_SECRET": os.getenv("SPACES_SECRET")
    }

@app.get("/test")
def test():
    return {"message": "Server is running"}

@app.get("/routes")
async def get_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append({
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods),
                "endpoint": route.endpoint.__name__ if route.endpoint else None,
                "tags": route.tags,
            })
    
    # Sort routes by path for better readability
    routes.sort(key=lambda x: x["path"])
    
    logger.info("Current routes:")
    for route in routes:
        logger.info(f"{', '.join(route['methods'])} {route['path']}")
    
    return {"routes": routes}

# Add a middleware to log all requests
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response