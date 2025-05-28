# ============================================================================
# shared/__init__.py - Simple exports
# ============================================================================

# Empty for now, we'll add as we build

# ============================================================================
# shared/auth.py - Simple authentication
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