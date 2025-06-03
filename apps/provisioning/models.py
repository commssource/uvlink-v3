from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, Index
from shared.database import Base
from datetime import datetime
from zoneinfo import ZoneInfo

class Provisioning(Base):
    __tablename__ = "provisioning"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(255), nullable=False)
    make = Column(String(50), nullable=False)
    model = Column(String(50), nullable=False)
    mac_address = Column(String(17), nullable=False, unique=True, index=True)
    username = Column(String(50), nullable=False)
    password = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(ZoneInfo("UTC")), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=True)  # Only set on updates
    status = Column(Boolean, default=True)
    approved = Column(Boolean, default=False)  # New field to track if MAC is approved

    # New fields for provisioning tracking
    provisioning_request = Column(String, nullable=True)  # Stores user-agent
    ip_address = Column(String, nullable=True)  # Stores x-forwarded-for
    provisioning_status = Column(String, nullable=True)  # Stores 'OK' or 'FAILED'
    last_provisioning_attempt = Column(DateTime(timezone=True), nullable=True)  # Timestamp of last attempt
    request_date = Column(DateTime(timezone=True), nullable=True)  # Timestamp of last request

    # Add an index on mac_address for faster lookups
    __table_args__ = (Index("idx_mac_address", "mac_address"),)

    def __repr__(self):
        return f"<Provisioning(id={self.id}, mac_address={self.mac_address}, status={self.status}, approved={self.approved})>" 
