# ============================================================================
# apps/__init__.py - Import only what exists
# ============================================================================

# Only import endpoints for now
try:
    from .endpoints.routes import router as endpoints_router
    available_routers = {"endpoints": endpoints_router}
except ImportError:
    available_routers = {}

# We'll add other apps later
# from .dids.routes import router as dids_router
# from .queues.routes import router as queues_router
# etc.

__all__ = list(available_routers.keys())