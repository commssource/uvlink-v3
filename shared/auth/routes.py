# ============================================================================
# apps/auth/routes.py - Authentication routes
# ============================================================================

from fastapi import APIRouter, HTTPException, Depends, Form, status
from pydantic import BaseModel
from .jwt_auth import JWTBearer, create_access_token, create_refresh_token, verify_refresh_token
from fastapi.security import HTTPBasicCredentials
from .basic_auth import BasicAuth
from .api_auth import APIBearer
from .combined_auth import verify_combined_auth
from config import PROVISIONING_USERNAME, PROVISIONING_PASSWORD
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

class TokenRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/token", response_model=TokenResponse)
async def create_token(
    username: str = Form(...),
    password: str = Form(...)
):
    """Generate new access and refresh tokens"""
    try:
        # Validate username and password
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username and password are required"
            )

        # Here you would typically validate against your user database
        # For now, we'll just create tokens for any valid request
        token_data = {
            "sub": username,
            "permissions": ["read", "write", "admin"]
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        logger.info(f"Generated tokens for user: {username}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    except Exception as e:
        logger.error(f"Error generating tokens: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate tokens"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str = Form(...)
):
    """Generate new access token using refresh token"""
    try:
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token is required"
            )

        # Verify the refresh token
        payload = verify_refresh_token(refresh_token)
        
        # Create new access token
        token_data = {
            "sub": payload["sub"],
            "permissions": payload.get("permissions", ["read", "write", "admin"])
        }
        
        access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)
        
        logger.info(f"Refreshed tokens for user: {payload['sub']}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not refresh token"
        )

# Test routes for different authentication methods
@router.get("/test/jwt", response_model=dict)
async def test_jwt_auth(payload: dict = Depends(JWTBearer())):
    """Test JWT authentication"""
    return {
        "message": "JWT authentication successful",
        "user": payload
    }

@router.get("/test/api", response_model=dict)
async def test_api_auth(api_key: str = Depends(APIBearer())):
    """Test API key authentication"""
    return {
        "message": "API key authentication successful",
        "key": api_key
    }

@router.get("/test/basic", response_model=dict)
async def test_basic_auth(credentials: HTTPBasicCredentials = Depends(BasicAuth())):
    """Test Basic authentication"""
    return {
        "message": "Basic authentication successful",
        "username": credentials.username
    }

@router.get("/test/combined", response_model=dict)
async def test_combined_auth(auth: dict = Depends(verify_combined_auth)):
    """Test Combined authentication"""
    return {
        "message": "Combined authentication successful",
        "auth_type": auth.get("type")
    }