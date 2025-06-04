# ============================================================================
# shared/auth/__init__.py - Authentication package
# ============================================================================ 

import jwt
from datetime import datetime, timedelta, UTC
from typing import Optional, Union, Dict, Any
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_DELTA, API_KEY
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    :param data: dict of claims (e.g., {"sub": "user_id"})
    :param expires_delta: optional timedelta for token expiry
    :return: JWT as a string
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or JWT_EXPIRATION_DELTA)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.
    :param data: dict of claims (e.g., {"sub": "user_id"})
    :param expires_delta: optional timedelta for token expiry
    :return: JWT as a string
    """
    to_encode = data.copy()
    # Refresh tokens typically have longer expiry
    expire = datetime.now(UTC) + (expires_delta or timedelta(days=30))
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API key authentication"""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return credentials.credentials

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token authentication"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Verify token type
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
            
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

def verify_refresh_token(token: str) -> dict:
    """Verify refresh token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Verify token type
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
            
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

def verify_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Union[str, dict]:
    """
    Accept either a valid JWT token or a valid API key.
    Returns the JWT payload (dict) or the API key (str).
    """
    # Try JWT first
    try:
        return verify_token(credentials)
    except HTTPException:
        # If JWT fails, try API key
        try:
            return verify_api_key(credentials)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )