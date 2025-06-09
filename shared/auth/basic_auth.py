from fastapi import HTTPException, Depends, status, Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from config import PROVISIONING_USERNAME, PROVISIONING_PASSWORD
import logging

logger = logging.getLogger(__name__)

class BasicAuth(HTTPBasic):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, credentials: HTTPBasicCredentials = Depends(HTTPBasic())) -> HTTPBasicCredentials:
        return verify_basic_auth(credentials)

async def verify_basic_auth(credentials: HTTPBasicCredentials) -> dict:
    """Verify basic authentication credentials for provisioning"""
    if credentials.username == PROVISIONING_USERNAME and credentials.password == PROVISIONING_PASSWORD:
        return {"type": "basic", "username": credentials.username}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid basic auth credentials"
    )
