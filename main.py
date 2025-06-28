# ============================================================================
# main.py - FastAPI Application with PJSIP Configuration Management
# ============================================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys
from pathlib import Path

# Import your modules
from config import Settings, get_settings
from apps.endpoints.routes import (
    router as pjsip_router, 
    initialize_managers,
    value_error_handler,
    file_not_found_handler
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pjsip_api.log')
    ]
)

logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup
    logger.info("Starting PJSIP Configuration API...")
    
    try:
        # Initialize settings
        settings = get_settings()
        
        # Initialize PJSIP managers
        await initialize_managers(settings)
        
        logger.info("PJSIP Configuration API started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down PJSIP Configuration API...")


# Create FastAPI application
app = FastAPI(
    title="PJSIP Configuration Management API",
    description="""
    A comprehensive REST API for managing Asterisk PJSIP configurations using Jinja2 templates.
    
    ## Features
    
    * **Endpoint Management**: Create, read, update, and delete PJSIP endpoints
    * **Template System**: Manage Jinja2 templates for configuration generation
    * **Advanced Filtering**: Filter and search endpoints with multiple criteria
    * **Bulk Operations**: Create multiple endpoints at once
    * **Configuration Validation**: Validate templates and generated configurations
    * **Backup Management**: Create and manage configuration backups
    * **Statistics**: Get insights into your PJSIP configuration
    
    ## Endpoint Types Supported
    
    * **Basic SIP Endpoints**: Standard SIP phones and devices
    * **WebRTC Endpoints**: Browser-based WebRTC clients
    * **SIP Trunks**: Provider connections and trunk lines
    * **Conference Rooms**: Audio conferencing endpoints
    * **Custom Types**: Create your own endpoint types with custom templates
    
    ## Authentication
    
    This API supports various authentication methods. Configure authentication
    in your settings file.
    """,
    version="1.0.0",
    contact={
        "name": "PJSIP Configuration API",
        "email": "admin@yourcompany.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(pjsip_router)

# Register exception handlers
app.add_exception_handler(ValueError, value_error_handler)
app.add_exception_handler(FileNotFoundError, file_not_found_handler)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "PJSIP Configuration Management API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "openapi_url": "/openapi.json",
        "endpoints": {
            "endpoints": "/api/v1/pjsip/endpoints",
            "templates": "/api/v1/pjsip/templates",
            "health": "/api/v1/pjsip/health",
            "stats": "/api/v1/pjsip/stats"
        }
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error",
            "timestamp": str(request.url),
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "service": "PJSIP Configuration API",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    
    # Development server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )