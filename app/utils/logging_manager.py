# main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Import logging manager first, before any other imports
from app.utils.logging_manager import log_manager, get_logger

# Apply the patches to control all logging behavior
log_manager.patch_all()

# Get a logger for this module
logger = get_logger()

# Create the FastAPI app
app = FastAPI(
    title="RYZE.ai API",
    description="Backend API for RYZE.ai",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import all routers after logging is configured
from app.routers import (
    login,
    profile,
    projects,
    # ...other router imports
)

# Register routers
app.include_router(login.router, prefix="/auth", tags=["Authentication"])
app.include_router(profile.router, prefix="/profile", tags=["Profile"])
app.include_router(projects.router, prefix="/projects", tags=["Projects"])
# ...register other routers

@app.get("/")
async def root():
    # This will respect production logging levels
    logger.debug("Debug message - won't show in production")
    logger.info("Info message - won't show in production")
    logger.warning("Warning message - will show in production")
    
    return {"message": "Welcome to RYZE.ai API"}

if __name__ == "__main__":
    log_level = "warning" if log_manager.is_production else "info"
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level=log_level, reload=not log_manager.is_production)