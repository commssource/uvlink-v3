# ============================================================================
# apps/__init__.py
# ============================================================================

from .endpoints.routes import router as endpoints_router
# from .dids.routes import router as dids_router
# from .queues.routes import router as queues_router
# from .reports.routes import router as reports_router
# from .ivr.routes import router as ivr_router
from .system.routes import router as system_router

__all__ = [
    "endpoints_router",
    # "dids_router", 
    # "queues_router",
    # "reports_router",
    # "ivr_router",
    "system_router"
]
