from fastapi import FastAPI
import logging
from app.routers import register, login, post, vote, newsletter, video_upload, display_videos, notes
from app.database import engine, Base
from app.config import settings
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from fastapi.routing import APIRoute
from app.database import engine

# Set up logging before application setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if running in production or local environment
env = os.getenv('ENV', 'local')  # Default to 'local' if ENV is not set

if env == 'local':
    # Use the absolute path for local development
    dotenv_path = 'C:/Users/dahern/Documents/RYZE.AI/fastapi/.env'
    load_dotenv(dotenv_path)
    logger.info(f"Loaded environment variables from .env file (local): {dotenv_path}")
else:
    # Use the .env file from the home directory on the Ubuntu server
    dotenv_path = os.path.expanduser('~/.env')
    load_dotenv(dotenv_path)
    logger.info(f"Loaded environment variables from .env file (production): {dotenv_path}")

# Log all environment variables from .env file to ensure they are loaded correctly
logger.info(f"Database Hostname: {os.getenv('DATABASE_HOSTNAME')}")
logger.info(f"Database Port: {os.getenv('DATABASE_PORT')}")
logger.info(f"Database Name: {os.getenv('DATABASE_NAME')}")
logger.info(f"Database Username: {os.getenv('DATABASE_USERNAME')}")
logger.info(f"Database Password: {os.getenv('DATABASE_PASSWORD')}")
logger.info(f"Secret Key: {os.getenv('SECRET_KEY')}")
logger.info(f"Algorithm: {os.getenv('ALGORITHM')}")
logger.info(f"Access Token Expiry: {os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')}")
logger.info(f"Spaces Token: {os.getenv('SPACES_TOKEN')}")
logger.info(f"Spaces Name: {os.getenv('SPACES_NAME')}")
logger.info(f"Spaces Region: {os.getenv('SPACES_REGION')}")
logger.info(f"Spaces Endpoint: {os.getenv('SPACES_ENDPOINT')}")
logger.info(f"Spaces Bucket: {os.getenv('SPACES_BUCKET')}")
logger.info(f"Local Video Upload Dir: {os.getenv('LOCAL_VIDEO_UPLOAD_DIR')}")

db_url = f"postgresql://{os.getenv('DATABASE_USERNAME')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_HOSTNAME')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_NAME')}"
db_url_parts = db_url.split('@')
if len(db_url_parts) > 1:
    masked_db_url = f"{db_url_parts[0].split(':')[0]}:****@{db_url_parts[1]}"
else:
    masked_db_url = db_url.split(':')[0] + ':****'
logger.info(f"Database URL: {masked_db_url}")

logger.info(f"Running in {env.upper()} environment")

logger.info(f"Connecting to {os.getenv('DATABASE_NAME')} database on {os.getenv('DATABASE_HOSTNAME')}:{os.getenv('DATABASE_PORT')} as user {os.getenv('DATABASE_USERNAME')}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    Base.metadata.create_all(bind=engine)

    for route in app.routes:
        logger.info(f"Route: {route.path} | Methods: {route.methods} | Name: {route.name}")

    yield
    logger.info("Application shutdown")

app = FastAPI(lifespan=lifespan)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ryze.ai",         # Production frontend (apex domain)
        "https://www.ryze.ai",     # Production frontend (www subdomain)
        "http://127.0.0.1:8000",   # Local backend (API)
        "http://localhost:3000",   # Local frontend (React dev server)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(register.router, prefix="/auth")
app.include_router(login.router, prefix="/auth")
app.include_router(post.router)
app.include_router(vote.router)
app.include_router(newsletter.router, prefix="/newsletter")
app.include_router(video_upload.router)
app.include_router(display_videos.router)
app.include_router(notes.router, prefix="/notes")

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
                    "methods": route.methods
                }
            )
    return {"routes": routes}


@app.get("/db-info")
async def get_db_info():
    return {
        "database_url": str(engine.url),
        "pool_size": engine.pool.size(),
        "pool_timeout": engine.pool.timeout(),
    }
