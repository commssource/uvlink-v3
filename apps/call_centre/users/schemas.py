from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime

class CallCentreUserBase(BaseModel):
    user_name: str
    user_id: str
    pin: Optional[str] = None
    mac_address: Optional[str] = None
    caller_id: Optional[str] = None
    endpoint: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[int] = 1
    trunk_id: Optional[str] = None
    roles: Optional[str] = None

class CallCentreUserCreate(CallCentreUserBase):
    password: str  # For initial password setting

class CallCentreUserUpdate(BaseModel):
    user_name: Optional[str] = None
    pin: Optional[str] = None
    mac_address: Optional[str] = None
    caller_id: Optional[str] = None
    endpoint: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[int] = None
    trunk_id: Optional[str] = None
    roles: Optional[str] = None
    password: Optional[str] = None

class CallCentreUserResponse(CallCentreUserBase):
    id: int
    login_time: Optional[datetime] = None
    logout_time: Optional[datetime] = None
    status: str  # Changed to str for response

    @field_validator('status', mode='before')
    @classmethod
    def convert_status_to_string(cls, v):
        if isinstance(v, int):
            return str(v)
        return v

    class Config:
        from_attributes = True
