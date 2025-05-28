# ============================================================================
# apps/endpoints/schemas.py - Endpoint Pydantic schemas
# ============================================================================

from pydantic import BaseModel, Field, validator
from typing import List, Optional
import re

class EndpointBase(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, regex=r'^[a-zA-Z0-9_-]+$')
    username: str = Field(..., min_length=1, max_length=50, regex=r'^[a-zA-Z0-9_@.-]+$')
    context: str = Field(default="internal", regex=r'^[a-zA-Z0-9_-]+$')
    codecs: List[str] = Field(default=["ulaw", "alaw"])
    max_contacts: int = Field(default=1, ge=1, le=10)
    callerid: Optional[str] = Field(None, max_length=100)

    @validator('codecs')
    def validate_codecs(cls, v):
        allowed_codecs = ['ulaw', 'alaw', 'g722', 'g729', 'gsm', 'opus']
        for codec in v:
            if codec not in allowed_codecs:
                raise ValueError(f'Invalid codec: {codec}')
        return v

    @validator('callerid')
    def validate_callerid(cls, v):
        if v and not re.match(r'^[\w\s<>@.-]+$', v):
            raise ValueError('Invalid caller ID format')
        return v

class EndpointCreate(EndpointBase):
    password: str = Field(..., min_length=8, max_length=128)

class EndpointUpdate(EndpointBase):
    password: Optional[str] = Field(None, min_length=8, max_length=128)

class Endpoint(EndpointBase):
    password: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class EndpointsList(BaseModel):
    endpoints: List[Endpoint]

class EndpointValidation(BaseModel):
    endpoint_id: str
    exists: bool
    available: bool
