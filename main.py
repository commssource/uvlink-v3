# ============================================================================
# Updated main.py - Better error handling
# ============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from config import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION,
    CORS_ORIGINS, HOST, PORT, LOG_LEVEL
)

# Initialize database
from shared.database import init_database

# Setup logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import endpoints router
try:
    from apps.endpoints.routes import router as endpoints_router
    app.include_router(endpoints_router, prefix="/api/v1")
    logger.info("✅ Endpoints app loaded")
except ImportError as e:
    logger.error(f"❌ Failed to load endpoints app: {e}")

@app.get("/")
async def root():
    return {
        "message": f"{APP_NAME} is running",
        "version": APP_VERSION,
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    try:
        from shared.database import engine
        # Quick connection test
        with engine.connect():
            pass
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy", 
        "database": db_status,
        "version": APP_VERSION
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("🚀 Starting Asterisk Management Platform...")
    
    # Initialize database
    if init_database():
        logger.info("✅ Database ready")
    else:
        logger.warning("⚠️ Database initialization had issues")

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True, log_level=LOG_LEVEL)