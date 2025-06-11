from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, Index, Text
from shared.database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

class Provisioning(Base):
    __tablename__ = "provisioning_ignore"

    id = Column(Integer, primary_key=True, index=True)
    mac_address = Column(String(12), unique=True, index=True)
    endpoint = Column(String(255), nullable=True)  # Allow NULL values
    make = Column(String(50), nullable=True)       # Allow NULL values
    model = Column(String(50), nullable=True)      # Allow NULL values
    username = Column(String(50), nullable=False)
    password = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(Boolean, default=True)

    # New fields for provisioning tracking
    device = Column(Text)  # For user agent
    ip_address = Column(String(45))  # IPv6 addresses can be up to 45 chars
    provisioning_status = Column(String(20), default="PENDING")  # PENDING, OK, FAILED
    last_provisioning_attempt = Column(DateTime)
    request_date = Column(DateTime, default=datetime.utcnow)
    approved = Column(Boolean, default=False)

    # Add an index on mac_address for faster lookups
    __table_args__ = (Index("idx_mac_address", "mac_address"),)

    def __repr__(self):
        return f"<Provisioning(id={self.id}, mac_address={self.mac_address}, status={self.status}, approved={self.approved})>" 
    
#==============================Provisioning Device===========================
class ProvisioningDevice(Base):
    __tablename__ = "provisioning"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    endpoint = Column(String(50), nullable=False, index=True)
    make = Column(String(50), nullable=False)
    model = Column(String(50), nullable=False)
    mac_address = Column(String(17), nullable=False, unique=True, index=True)  # MAC address format: XX:XX:XX:XX:XX:XX
    status = Column(Boolean, nullable=False, default=True)
    username = Column(String(100), nullable=False)
    password = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())