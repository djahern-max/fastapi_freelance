from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from app.routers import (
    register,
    login,
    video_upload,
    display_videos,
    projects,
    comments,
    conversations,
    profile,
)
from app.routers import request as requests_router
from fastapi.routing import APIRoute
import logging
from fastapi.responses import JSONResponse, PlainTextResponse
import datetime
from typing import List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a utility router with tags
utility_router = APIRouter(
    prefix="/utils",  # Optional: add a prefix for utility endpoints
    tags=["Utilities"],
    responses={404: {"description": "Not found"}},
)


@utility_router.get(
    "/debug",
    summary="Get debug information",
    description="Returns configuration information for spaces",
    response_description="Debug information about spaces configuration",
)
def debug_spaces():
    return {
        "SPACES_BUCKET": os.getenv("SPACES_BUCKET"),
        "SPACES_REGION": os.getenv("SPACES_REGION"),
        "SPACES_KEY": os.getenv("SPACES_KEY"),
        "SPACES_SECRET": os.getenv("SPACES_SECRET"),
    }


@utility_router.get(
    "/test",
    summary="Test endpoint",
    description="Simple endpoint to verify API is running",
    response_description="Server status message",
)
def test():
    return {"message": "Server is running"}


@utility_router.get(
    "/routes",
    response_class=JSONResponse,
    summary="Get all API routes in JSON format",
    description="Returns a list of all available API routes with detailed information",
    response_description="List of routes with their details",
)
async def get_routes():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(
                {
                    "path": route.path,
                    "name": route.name,
                    "methods": list(route.methods),
                    "endpoint": route.endpoint.__name__ if route.endpoint else None,
                    "tags": route.tags,
                }
            )
    routes.sort(key=lambda x: x["path"])
    logger.info(f"Routes endpoint called, returning {len(routes)} routes")
    return JSONResponse(
        content={"routes": routes},
        headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
    )


@utility_router.get(
    "/routes-text",
    response_class=PlainTextResponse,
    summary="Get all API routes in text format",
    description="Returns a plain text list of all available API routes",
    response_description="Text list of routes",
)
async def get_routes_text():
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append(f"{', '.join(route.methods)} {route.path}")
    sorted_routes = sorted(routes)
    logger.info(f"Routes-text endpoint called, returning {len(routes)} routes")
    return PlainTextResponse(
        "\n".join(sorted_routes),
        headers={"Content-Type": "text/plain", "Access-Control-Allow-Origin": "*"},
    )


@utility_router.get(
    "/api-test",
    summary="Test API functionality",
    description="Endpoint to verify API is working correctly",
    response_description="API status information",
)
async def api_test():
    return JSONResponse(
        content={"status": "ok", "message": "API endpoint working"},
        headers={"Content-Type": "application/json"},
    )


@utility_router.get(
    "/api-status",
    summary="Get detailed API status",
    description="Returns comprehensive information about the API's current status",
    response_description="Detailed API status information",
)
async def api_status():
    route_count = len([r for r in app.routes if isinstance(r, APIRoute)])
    return JSONResponse(
        content={
            "status": "ok",
            "message": "API is running",
            "route_count": route_count,
            "timestamp": datetime.datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "production"),
        },
        headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
    )


# Initialize FastAPI app with lifespan and docs URL configuration
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Available routes:")
    for route in app.routes:
        if isinstance(route, APIRoute):
            logger.info(f"{', '.join(route.methods)} {route.path}")
    yield


app = FastAPI(
    title="RYZE.AI API",
    description="API for RYZE.AI platform",
    version="1.0.0",
    docs_url="/api/docs",  # Change the docs URL
    redoc_url="/api/redoc",  # Change the redoc URL
    openapi_url="/api/openapi.json",  # Change the OpenAPI URL
    lifespan=lifespan,
)

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
    (profile.router, ""),
    (utility_router, ""),
]

for router, prefix in routers_with_prefixes:
    app.include_router(router, prefix=prefix)
    logger.info(f"\nRoutes for {router.__class__.__name__}:")
    log_router_routes(router, prefix)


# Add a middleware to log all requests
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response
