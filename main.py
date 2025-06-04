# ============================================================================
# Updated main.py - Better error handling
# ============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from contextlib import asynccontextmanager

from config import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION,
    CORS_ORIGINS, HOST, PORT, LOG_LEVEL
)
# Initialize database
from shared.database import init_database

# Import routers
from apps.endpoints.routes import router as endpoints_router
from shared.auth.routes import router as auth_router
from apps.provisioning.routes import router as provisioning_router, config_router, prov_router
from apps.inbound_call_routing import router as inbound_call_routing_router

# Setup logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application on startup and cleanup on shutdown"""
    logger.info("🚀 Starting Asterisk Management Platform...")
    
    # Initialize database
    if init_database():
        logger.info("✅ Database ready")
    else:
        logger.warning("⚠️ Database initialization had issues")
    
    yield

# Create FastAPI app
app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    # Include routers
    app.include_router(endpoints_router)
    app.include_router(auth_router)
    app.include_router(provisioning_router, tags=["provisioning"])
    app.include_router(config_router)
    app.include_router(prov_router)
    app.include_router(inbound_call_routing_router)
    
    logger.info("✅ Endpoints app loaded")
    logger.info("✅ Auth app loaded")
    logger.info("✅ Provisioning app loaded")
    logger.info("✅ Inbound Call Routing app loaded")
except ImportError as e:
    logger.error(f"❌ Failed to load apps: {e}")


@app.get("/")
async def root():
    return {
        "message": f"{APP_NAME} is running",
        "version": "UVL0.098",
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

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level=LOG_LEVEL,
        reload_dirs=["."],  # Only watch the current directory
        reload_excludes=["venv/*"]  # Exclude the virtual environment
    )