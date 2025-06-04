from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from shared.database import get_db
from apps.provisioning.models import Provisioning
import logging

logger = logging.getLogger(__name__)

security = HTTPBasic()

async def verify_basic_auth(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
    mac_address: str = None
):
    """Verify basic auth against provisioning table"""
    try:
        if not mac_address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MAC address is required"
            )

        # Get the provisioning record
        provisioning = db.query(Provisioning).filter(
            Provisioning.mac_address == mac_address
        ).first()
        
        if not provisioning:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provisioning record not found for MAC: {mac_address}"
            )

        # Verify credentials
        if not provisioning.username or not provisioning.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Provisioning record has no credentials configured"
            )

        # Check username and password
        if credentials.username != provisioning.username or credentials.password != provisioning.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Basic"}
            )
        
        return credentials

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying basic auth: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying credentials: {str(e)}"
        ) 