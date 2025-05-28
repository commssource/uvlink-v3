from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import re

class EndpointBase(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    username: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_@.-]+$')
    context: str = Field(default="internal", pattern=r'^[a-zA-Z0-9_-]+$')
    codecs: List[str] = Field(default=["ulaw", "alaw"])
    max_contacts: int = Field(default=1, ge=1, le=10)
    callerid: Optional[str] = Field(None, max_length=100)

    @field_validator('codecs')
    @classmethod
    def validate_codecs(cls, v):
        allowed_codecs = ['ulaw', 'alaw', 'g722', 'g729', 'gsm', 'opus']
        for codec in v:
            if codec not in allowed_codecs:
                raise ValueError(f'Invalid codec: {codec}')
        return v

    @field_validator('callerid')
    @classmethod
    def validate_callerid(cls, v):
        if v and not re.match(r'^[\w\s<>@.-]+$', v):
            raise ValueError('Invalid caller ID format')
        return v

class EndpointCreate(EndpointBase):
    password: str = Field(..., min_length=8, max_length=128)

class EndpointUpdate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_@.-]+$')
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    context: str = Field(default="internal", pattern=r'^[a-zA-Z0-9_-]+$')
    codecs: List[str] = Field(default=["ulaw", "alaw"])
    max_contacts: int = Field(default=1, ge=1, le=10)
    callerid: Optional[str] = Field(None, max_length=100)

    @field_validator('codecs')
    @classmethod
    def validate_codecs(cls, v):
        allowed_codecs = ['ulaw', 'alaw', 'g722', 'g729', 'gsm', 'opus']
        for codec in v:
            if codec not in allowed_codecs:
                raise ValueError(f'Invalid codec: {codec}')
        return v

    @field_validator('callerid')
    @classmethod
    def validate_callerid(cls, v):
        if v and not re.match(r'^[\w\s<>@.-]+$', v):
            raise ValueError('Invalid caller ID format')
        return v

class Endpoint(EndpointBase):
    password: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

class EndpointsList(BaseModel):
    endpoints: List[Endpoint]

class StatusResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

class ReloadResponse(BaseModel):
    success: bool
    message: str
    output: Optional[str] = None

class ConfigResponse(BaseModel):
    success: bool
    config: str
    timestamp: str

class EndpointValidation(BaseModel):
    endpoint_id: str
    exists: bool
    available: bool