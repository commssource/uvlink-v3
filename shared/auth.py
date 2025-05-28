# ============================================================================
# shared/auth.py - Authentication middleware
# ============================================================================

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import API_KEY

security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API key authentication"""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials

def get_current_user(api_key: str = Depends(verify_api_key)) -> dict:
    """Get current authenticated user info"""
    return {
        "authenticated": True,
        "api_key": api_key[:8] + "...",  # Masked for security
        "permissions": ["read", "write", "admin"]  # Could be from database
    }

