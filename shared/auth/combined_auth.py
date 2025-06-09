from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPBasic, HTTPAuthorizationCredentials, HTTPBasicCredentials
from typing import Dict, Any, Optional
from config import API_KEY, PROVISIONING_USERNAME, PROVISIONING_PASSWORD
import jwt
from config import JWT_SECRET, JWT_ALGORITHM
import logging
from fastapi.responses import Response
from fastapi.security import HTTPBasicCredentials, HTTPBasic

logger = logging.getLogger(__name__)

# Create instances of both auth schemes
bearer_auth = HTTPBearer(auto_error=False)
basic_auth = HTTPBasic(auto_error=True)  # Set to True to trigger browser prompt

async def verify_combined_auth(
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_auth),
    basic: Optional[HTTPBasicCredentials] = Depends(basic_auth)
) -> Dict[str, Any]:
    """Verify either JWT, API key, or Basic auth"""
    
    # Try Basic auth first
    if basic:
        logger.info(f"Attempting basic auth with username: {basic.username}")
        if basic.username == PROVISIONING_USERNAME and basic.password == PROVISIONING_PASSWORD:
            return {"type": "basic", "username": basic.username}
        else:
            logger.error(f"Basic auth failed for user: {basic.username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid basic auth credentials"
            )
    
    # If no basic auth, try bearer token
    if bearer:
        try:
            # Try JWT
            try:
                token = bearer.credentials
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                if payload.get("type") != "access":
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token type"
                    )
                return payload
            except jwt.PyJWTError:
                # If JWT fails, try API key
                if bearer.credentials == API_KEY:
                    return {"type": "api_key"}
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid bearer token"
                    )
        except Exception as e:
            logger.error(f"Bearer auth error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    
    # If neither auth method provided, return 401 with WWW-Authenticate header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials",
        headers={"WWW-Authenticate": "Basic"}
    )
