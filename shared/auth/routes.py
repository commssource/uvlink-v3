# ============================================================================
# apps/auth/routes.py - Authentication routes
# ============================================================================

from fastapi import APIRouter, HTTPException, Depends, Form
from pydantic import BaseModel
from . import create_access_token, create_refresh_token, verify_refresh_token

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
    # Here you would typically validate the username and password
    # For now, we'll just create tokens for any valid request
    token_data = {
        "sub": username,
        "permissions": ["read", "write", "admin"]
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str = Form(...)
):
    """Generate new access token using refresh token"""
    try:
        # Verify the refresh token
        payload = verify_refresh_token(refresh_token)
        
        # Create new access token
        token_data = {
            "sub": payload["sub"],
            "permissions": payload.get("permissions", ["read", "write", "admin"])
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Could not refresh token"
        )