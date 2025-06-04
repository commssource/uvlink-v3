from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

class ProvisioningBase(BaseModel):
    endpoint: str = Field(..., description="Endpoint ID")
    make: str = Field(..., description="Phone make (e.g., yealink)")
    model: str = Field(..., description="Phone model (e.g., T48S)")
    mac_address: str = Field(..., description="12-character MAC address")
    status: bool = Field(True, description="Provisioning status")

class ProvisioningCreate(ProvisioningBase):
    pass

class ProvisioningUpdate(BaseModel):
    endpoint: Optional[str] = Field(None, description="Endpoint ID")
    make: Optional[str] = Field(None, description="Phone make (e.g., yealink)")
    model: Optional[str] = Field(None, description="Phone model (e.g., T48S)")
    mac_address: Optional[str] = Field(None, description="12-character MAC address")
    username: Optional[str] = Field(None, description="Username")
    password: Optional[str] = Field(None, description="Password")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    status: Optional[bool] = Field(None, description="Provisioning status")

class Provisioning(ProvisioningBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "endpoint": "201",
                "make": "yealink",
                "model": "T48S",
                "mac_address": "0015651234AP",
                "status": True
            }
        }

class ProvisioningResponse(BaseModel):
    id: int
    endpoint: str
    make: str
    model: str
    mac_address: str
    status: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    approved: Optional[bool] = False
    provisioning_request: Optional[str]
    ip_address: Optional[str]
    provisioning_status: Optional[str]
    last_provisioning_attempt: Optional[datetime]
    request_date: Optional[datetime]