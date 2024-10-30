from fastapi import FastAPI
import logging
from app.routers import register, login, post, vote, newsletter, video_upload, display_videos, notes, projects  # Import projects router
from app.database import engine, Base
from app.config import settings
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from fastapi.routing import APIRoute

# Set up logging before application setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if running in production or local environment
env = os.getenv('ENV', 'local')  # Default to 'local' if ENV is not set

if env == 'local':
    dotenv_path = 'C:/Users/dahern/Documents/RYZE.AI/fastapi/.env'
    load_dotenv(dotenv_path)
    logger.info(f"Loaded environment variables from .env file (local): {dotenv_path}")
else:
    dotenv_path = os.path.expanduser('~/.env')
    load_dotenv(dotenv_path)
    logger.info(f"Loaded environment variables from .env file (production): {dotenv_path}")

# Log environment variables
logger.info(f"Database Hostname: {os.getenv('DATABASE_HOSTNAME')}")
logger.info(f"Database Port: {os.getenv('DATABASE_PORT')}")
logger.info(f"Database Name: {os.getenv('DATABASE_NAME')}")
logger.info(f"Database Username: {os.getenv('DATABASE_USERNAME')}")
logger.info(f"Database Password: {os.getenv('DATABASE_PASSWORD')}")
logger.info(f"Secret Key: {os.getenv('SECRET_KEY')}")
logger.info(f"Spaces Bucket: {os.getenv('SPACES_BUCKET')}")

# Create masked database URL for logging
db_url = f"postgresql://{os.getenv('DATABASE_USERNAME')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_HOSTNAME')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_NAME')}"
db_url_parts = db_url.split('@')
masked_db_url = f"{db_url_parts[0].split(':')[0]}:****@{db_url_parts[1]}" if len(db_url_parts) > 1 else db_url.split(':')[0] + ':****'
logger.info(f"Database URL: {masked_db_url}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    Base.metadata.create_all(bind=engine)

    for route in app.routes:
        logger.info(f"Route: {route.path} | Methods: {route.methods} | Name: {route.name}")

    yield
    logger.info("Application shutdown")

app = FastAPI(lifespan=lifespan)

# Set up CORS
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ryze.ai",
        "https://www.ryze.ai",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://localhost:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(register.router, prefix="/auth")
app.include_router(login.router, prefix="/auth")
app.include_router(post.router)
app.include_router(vote.router)
logger.info("About to register newsletter router")
try:
    app.include_router(newsletter.router, prefix="/newsletter")
    logger.info("Successfully registered newsletter router")
except Exception as e:
    logger.error(f"Failed to register newsletter router: {e}")
app.include_router(video_upload.router)
app.include_router(display_videos.router)
print("Registering notes router")
app.include_router(notes.router)
print("Notes router registered")
app.include_router(projects.router)

# Debug route to check Spaces configuration
@app.get("/debug")
def debug_spaces():
    logger.info("Debug route was called")
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

# Route to get database information
@app.get("/db-info")
async def get_db_info():
    return {
        "database_url": str(engine.url),
        "pool_size": engine.pool.size(),
        "pool_timeout": engine.pool.timeout(),
    }
