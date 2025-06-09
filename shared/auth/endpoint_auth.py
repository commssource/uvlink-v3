from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .jwt_auth import verify_jwt_token
from .api_auth import verify_api_key
import logging

logger = logging.getLogger(__name__)

class EndpointAuth(HTTPBearer):
    def __init__(self, auto_error: bool = False):
        super().__init__(auto_error=auto_error)

    async def __call__(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))) -> dict:
        return await verify_endpoint_auth(credentials)

async def verify_endpoint_auth(credentials: HTTPAuthorizationCredentials) -> dict:
    """Verify either JWT token or API key for endpoint access"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials"
        )

    # Try JWT first
    try:
        return verify_jwt_token(credentials)
    except HTTPException:
        # If JWT fails, try API key
        try:
            return {"type": "api_key", "key": verify_api_key(credentials)}
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
