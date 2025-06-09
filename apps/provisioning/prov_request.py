from datetime import datetime
from fastapi import Request
from sqlalchemy.orm import Session
from .models import Provisioning
import logging

logger = logging.getLogger(__name__)

class ProvisioningRequestLogger:
    def __init__(self, db: Session):
        self.db = db

    async def log_request(self, mac_address: str, request: Request) -> Provisioning:
        """Log provisioning request details"""
        try:
            # Get client IP and user agent
            ip_address = request.client.host
            user_agent = request.headers.get("user-agent", "Unknown")
            
            # Log the request in the database
            provisioning_record = self.db.query(Provisioning).filter(
                Provisioning.mac_address == mac_address
            ).first()
            
            if provisioning_record:
                # Update existing record
                provisioning_record.ip_address = ip_address
                provisioning_record.device = user_agent
                provisioning_record.request_date = datetime.utcnow()
                provisioning_record.last_provisioning_attempt = datetime.utcnow()
            else:
                # Create new record with default values
                provisioning_record = Provisioning(
                    mac_address=mac_address,
                    ip_address=ip_address,
                    device=user_agent,
                    request_date=datetime.utcnow(),
                    last_provisioning_attempt=datetime.utcnow(),
                    endpoint=mac_address,  # Use MAC address as endpoint initially
                    make="Unknown",        # Default values for required fields
                    model="Unknown",
                    status=True,
                    approved=False,
                    provisioning_status="PENDING"
                )
                self.db.add(provisioning_record)
            
            self.db.commit()
            return provisioning_record

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error logging provisioning request: {str(e)}")
            raise

    def update_status(self, provisioning_record: Provisioning, status: str):
        """Update provisioning status"""
        try:
            provisioning_record.provisioning_status = status
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating provisioning status: {str(e)}")
            raise
