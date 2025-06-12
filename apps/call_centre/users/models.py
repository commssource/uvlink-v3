from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from shared.database import Base

class CallCentreUser(Base):
    __tablename__ = "call_centre_users"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String(255), nullable=False)
    user_id = Column(String(255), unique=True, nullable=False)
    pin = Column(String(255))
    mac_address = Column(String(255))
    caller_id = Column(String(255))
    endpoint = Column(String(255))
    email = Column(String(255))
    status = Column(Integer, default=1)
    login_time = Column(DateTime(timezone=True))
    logout_time = Column(DateTime(timezone=True))
    trunk_id = Column(String(255))
    roles = Column(String(255))
    hashed_password = Column(String(255))
