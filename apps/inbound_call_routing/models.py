from sqlalchemy import Column, Integer, String, Boolean
from shared.database import Base

class InboundCallRouting(Base):
    __tablename__ = "inbound_call_routing"

    id = Column(Integer, primary_key=True, index=True)
    did_number = Column(String(20), unique=True, index=True)
    client_name = Column(String(100))
    destination = Column(String(50))
    destination_value = Column(String(100))
    status = Column(Boolean, default=True) 