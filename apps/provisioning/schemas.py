from pydantic import BaseModel, field_validator, Field, BeforeValidator
from typing import List, Optional, Annotated
from datetime import datetime

# Base schema for common fields in provisioning
endpoint = str
make = str
model = str
mac_address = str
ip_address = str
username = str
password = str
status = bool

def validate_mac_address(v: str) -> str:
    if len(v) != 12:
        raise ValueError("MAC address must be exactly 12 characters long")
    if not v.isalnum():
        raise ValueError("MAC address must contain only alphanumeric characters")
    return v.upper()

# Schema for creating a new provisioning
class ProvisioningCreate(BaseModel):
   endpoint: Optional[str] = None
   make: Optional[str] = None
   model: Optional[str] = None
   mac_address: Annotated[str, BeforeValidator(validate_mac_address)] = Field(
        ...,
        min_length=12,
        max_length=12,
        description="12-character MAC address"
    )
   username: Optional[str] = None
   password: Optional[str] = None
   status: Optional[bool] = None

   model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "endpoint": "201",
                "make": "yealink",
                "model": "T48S",
                "mac_address": "249AD818CD92",
                "username": "phone_user",
                "password": "phone_pass",
                "status": True
            }
        }
    }

# Schema for updating a provisioning
class ProvisioningUpdate(BaseModel):
   endpoint: Optional[str] = None
   make: Optional[str] = None
   model: Optional[str] = None
   mac_address: Optional[str] = None
   ip_address: Optional[str] = None
   username: Optional[str] = None
   password: Optional[str] = None
   approved: Optional[bool] = False
   status: Optional[bool] = None

# Schema for provisioning response
class ProvisioningResponse(BaseModel):
   id: int
   endpoint: str
   make: Optional[str] = None
   model: Optional[str] = None
   mac_address: Optional[str] = None
   ip_address: Optional[str] = None
   username: Optional[str] = None
   password: Optional[str] = None
   device: Optional[str] = None
   created_at: Optional[datetime] = None
   updated_at: Optional[datetime] = None
   last_provisioning_attempt: Optional[datetime] = None
   approved: Optional[bool] = False  # Set default to False to match database
   status: Optional[bool] = None
   
