# ============================================================================
# apps/endpoints/models.py - Endpoint database models
# ============================================================================

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from shared.database import Base

class EndpointModel(Base):
    __tablename__ = "endpoints"

    id = Column(String(50), primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(128))
    context = Column(String(50), default="internal")
    codecs = Column(Text)  # JSON string of codec list
    max_contacts = Column(Integer, default=1)
    callerid = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
