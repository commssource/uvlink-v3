from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPBasic, HTTPAuthorizationCredentials, HTTPBasicCredentials
from typing import Dict, Any, Optional
from config import API_KEY, PROVISIONING_USERNAME, PROVISIONING_PASSWORD
import jwt
from config import JWT_SECRET, JWT_ALGORITHM
import logging

logger = logging.getLogger(__name__)

# Create instances of both auth schemes
bearer_auth = HTTPBearer(auto_error=False)  # Set to False to handle both JWT and API key
basic_auth = HTTPBasic(auto_error=False)    # Set to False to handle both auth methods

async def verify_combined_auth(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_auth),
    basic: Optional[HTTPBasicCredentials] = Depends(basic_auth)
) -> Dict[str, Any]:
    """Verify either JWT, API key, or Basic auth"""
    
    # Log the incoming request details
    logger.info("=== Authentication Attempt ===")
    auth_header = request.headers.get('authorization', '')
    logger.info(f"Authorization header: {auth_header}")
    
    # Try Bearer token first
    if bearer:
        try:
            token = bearer.credentials
            logger.info(f"Bearer token present: {token[:10]}...")
            
            # First try API key
            if token == API_KEY:
                logger.info("API key authentication successful")
                return {"type": "api_key"}
            
            # If not API key, try JWT
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                if payload.get("type") != "access":
                    logger.error("Invalid token type in JWT")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token type"
                    )
                logger.info("JWT authentication successful")
                return payload
            except jwt.PyJWTError as e:
                logger.error(f"JWT validation failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid JWT token"
                )
        except Exception as e:
            logger.error(f"Bearer auth error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    
    # If no bearer token, try Basic auth
    if basic:
        logger.info(f"Basic auth present: {basic.username}")
        if basic.username == PROVISIONING_USERNAME and basic.password == PROVISIONING_PASSWORD:
            logger.info("Basic auth successful")
            return {"type": "basic", "username": basic.username}
        else:
            logger.error(f"Basic auth failed for user: {basic.username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid basic auth credentials"
            )
    
    # If neither auth method provided
    logger.error("No authentication credentials provided")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials",
        headers={"WWW-Authenticate": "Basic"}
    )
