# ============================================================================
# main.py - Fixed Manager Initialization
# ============================================================================

from fastapi import FastAPI
from config import get_current_settings, print_configuration_summary
import logging
import asyncio

# Setup logging first
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app():
    """Create FastAPI application"""
    settings = get_current_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Asterisk Configuration Manager API",
        debug=settings.debug,
    )
    
    return app

# Create app
app = create_app()

@app.on_event("startup")
async def startup_event():
    """Initialize everything on startup"""
    try:
        settings = get_current_settings()
        logger.info("🚀 Starting Asterisk Configuration Manager...")
        
        print_configuration_summary(settings)
        
        # Import and initialize managers
        from shared.template_manager import UnifiedTemplateManager
        from apps.endpoints.pjsip_manager.config_manager import ConfigManager
        from apps.queues.queue_manager import QueueConfigManager
        
        # Initialize template manager
        template_dirs = settings.get_template_directories()
        template_manager = UnifiedTemplateManager(template_dirs)
        logger.info(f"✅ Template manager initialized with directories: {[str(d) for d in template_dirs]}")
        
        # Initialize PJSIP manager
        pjsip_manager = ConfigManager(settings, template_manager)
        logger.info("✅ PJSIP manager initialized")
        
        # Initialize Queue manager
        queue_manager = QueueConfigManager(settings, template_manager)
        logger.info("✅ Queue manager initialized")
        
        # Set managers in API modules (import the modules, not the routers)
        import apps.endpoints.routes as pjsip_routes
        pjsip_routes.set_managers(template_manager, pjsip_manager, settings)
        
        import apps.queues.routes as queue_routes
        queue_routes.set_managers(template_manager, queue_manager, settings)
        
        logger.info("🎉 All managers initialized and set successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize application: {e}")
        # Log the full traceback for debugging
        import traceback
        logger.error(traceback.format_exc())
        raise

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "message": "Asterisk Configuration Manager is running"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Asterisk Configuration Manager API",
        "docs": "/docs",
        "health": "/health",
        "endpoints": "/api/v1/pjsip/endpoints",
        "queues": "/api/v1/queues"
    }

# Include routers - import the router objects
from apps.endpoints.routes import router as pjsip_router
from apps.queues.routes import router as queue_router

app.include_router(pjsip_router)
app.include_router(queue_router)

if __name__ == "__main__":
    import uvicorn
    
    settings = get_current_settings()
    uvicorn_config = settings.get_uvicorn_config()
    
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    logger.info(f"Environment: {'Development' if settings.is_development() else 'Production'}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info("Access API docs at: http://localhost:8000/docs")
    logger.info("Test endpoints:")
    logger.info("  - GET  http://localhost:8000/health")
    logger.info("  - GET  http://localhost:8000/api/v1/pjsip/endpoints")
    logger.info("  - GET  http://localhost:8000/api/v1/queues")
    
    uvicorn.run("main:app", **uvicorn_config)