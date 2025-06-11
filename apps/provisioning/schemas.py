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
   
#======================================Azure Storage=====================================
class RecordCreate(BaseModel):
    content: str
    filename: Optional[str] = None
    tenant_name: Optional[str] = None

    class Config:
        # Add example for better API documentation
        schema_extra = {
            "example": {
                "content": "#!version:1.0.0.1\naccount.1.enable = 1\naccount.1.label = \"201\"\n...",
                "filename": "device_201.cfg",
                "tenant_name": "t-200"
            }
        }

class RecordResponse(BaseModel):
    filename: str
    blob_path: str
    url: str
    container: str
    tenant: str

class RecordListItem(BaseModel):
    filename: str
    blob_path: str
    size: int
    last_modified: str  # Changed to string to avoid datetime serialization issues
    url: str
    tenant: str

class RecordContent(BaseModel):
    content: str

#======================================Provisioning Config File and Endpoint API Calls=====================================
class DeviceProvisionRequest(BaseModel):
    endpoint: str
    make: str
    model: str
    mac_address: str
    status: bool = True
    username: str
    password: str

    class Config:
        schema_extra = {
            "example": {
                "endpoint": "202",
                "make": "yealink",
                "model": "T48S",
                "mac_address": "249ad818cd92",
                "status": True,
                "username": "phone_user",
                "password": "phone_pass"
            }
        }

class DeviceUpdateRequest(BaseModel):
    endpoint: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    mac_address: Optional[str] = None
    status: Optional[bool] = None
    username: Optional[str] = None
    password: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "endpoint": "203",
                "make": "yealink",
                "model": "T46S",
                "mac_address": "249ad818cd97",
                "status": False,
                "username": "new_phone_user",
                "password": "new_phone_pass"
            }
        }


class DeviceResponse(BaseModel):
    id: int
    endpoint: str
    make: str
    model: str
    mac_address: str
    status: bool
    username: str
    password: str
    created_at: Optional[str]
    updated_at: Optional[str]
    config_file_url: Optional[str] = None

class RecordCreate(BaseModel):
    content: str
    filename: Optional[str] = None
    tenant_name: Optional[str] = None

    class Config:
        # Add example for better API documentation
        schema_extra = {
            "example": {
                "content": "#!version:1.0.0.1\naccount.1.enable = 1\naccount.1.label = \"201\"\n...",
                "filename": "device_201.cfg",
                "tenant_name": "t-200"
            }
        }

class RecordResponse(BaseModel):
    filename: str
    blob_path: str
    url: str
    container: str
    tenant: str

class RecordListItem(BaseModel):
    filename: str
    blob_path: str
    size: int
    last_modified: str  # Changed to string to avoid datetime serialization issues
    url: str
    tenant: str

class RecordContent(BaseModel):
    content: str