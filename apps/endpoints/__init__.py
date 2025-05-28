# ============================================================================
# apps/endpoints/__init__.py
# ============================================================================

from .routes import router

__all__ = ["router"]

# ============================================================================
# main.py - Simplified main app
# ============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from config import (
    APP_NAME, APP_VERSION, APP_DESCRIPTION,
    CORS_ORIGINS, HOST, PORT, LOG_LEVEL
)

# Simple logging setup
logging.basicConfig(level=getattr(logging, LOG_LEVEL.upper()))

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

# Import and include routers
try:
    from apps.endpoints.routes import router as endpoints_router
    app.include_router(endpoints_router, prefix="/api/v1")
    print("✅ Endpoints app loaded")
except ImportError as e:
    print(f"❌ Failed to load endpoints app: {e}")

# Basic health check
@app.get("/")
async def root():
    """API status endpoint"""
    return {
        "success": True,
        "message": f"{APP_NAME} is running",
        "version": APP_VERSION,
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level=LOG_LEVEL
    )
