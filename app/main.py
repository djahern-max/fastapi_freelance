from fastapi import FastAPI, Request
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
    agreements,
    public_profile,
    request as requests_router,
)
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, PlainTextResponse

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    lifespan=lifespan,
    title="RYZE.AI API",
    description="API for RYZE.AI platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

# Register routers with their prefixes
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
    (agreements.router, ""),
    (public_profile.router, ""),
]

# Include all routers
for router, prefix in routers_with_prefixes:
    app.include_router(router, prefix=prefix)


@app.get("/debug")
def debug_spaces():
    return {
        "SPACES_BUCKET": os.getenv("SPACES_BUCKET"),
        "SPACES_REGION": os.getenv("SPACES_REGION"),
        "SPACES_KEY": os.getenv("SPACES_KEY"),
        "SPACES_SECRET": os.getenv("SPACES_SECRET"),
    }


@app.get("/test")
def test():
    return {"message": "Server is running"}


@app.get("/routes")
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
    return {"routes": routes}


# @app.get("/routes-text")
# async def get_routes_text():
#     routes = []
#     for route in app.routes:
#         if isinstance(route, APIRoute):
#             routes.append(f"{', '.join(route.methods)} {route.path}")
#     return PlainTextContent("\n".join(sorted(routes)))


@app.get("/api-test")
async def api_test():
    return JSONResponse(
        content={"status": "ok", "message": "API endpoint working"},
        headers={"Content-Type": "application/json"},
    )


@app.get("/routes-description", response_class=PlainTextResponse)
async def get_routes_description():
    """
    Returns a human-readable description of all the routes in the application.
    """
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            methods = ", ".join(route.methods)
            route_description = (
                f"Path: {route.path}\n"
                f"Methods: {methods}\n"
                f"Name: {route.name}\n"
                f"Tags: {', '.join(route.tags) if route.tags else 'None'}\n"
                f"Endpoint: {route.endpoint.__name__ if route.endpoint else 'None'}\n"
            )
            routes.append(route_description)

    # Join all routes' descriptions into a single plain text response
    return "\n".join(routes)
