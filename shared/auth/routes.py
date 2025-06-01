# ============================================================================
# apps/auth/routes.py - Authentication routes
# ============================================================================

from fastapi import APIRouter
from . import create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

@router.post("/token")
async def create_token():
    """Generate a new JWT token"""
    token_data = {
        "sub": "user123",
        "permissions": ["read", "write", "admin"]
    }
    access_token = create_access_token(token_data)
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }