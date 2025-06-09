from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, Index, Text
from shared.database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

class Provisioning(Base):
    __tablename__ = "provisioning"

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
