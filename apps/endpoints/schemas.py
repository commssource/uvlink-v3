from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import re

class AuthConfig(BaseModel):
    """Authentication configuration"""
    type: str = Field(default="auth")
    auth_type: str = Field(default="userpass")
    entity_type: str = Field(default="endpoint")
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)
    realm: Optional[str] = Field(None, max_length=100)

class AORConfig(BaseModel):
    """Address of Record configuration"""
    type: str = Field(default="aor")
    entity_type: str = Field(default="endpoint")
    max_contacts: int = Field(default=2, ge=1, le=10)
    qualify_frequency: Optional[int] = Field(default=60, ge=0, le=300)
    authenticate_qualify: Optional[str] = Field(default="no")
    default_expiration: Optional[int] = Field(default=3600)
    minimum_expiration: Optional[int] = Field(default=60)
    maximum_expiration: Optional[int] = Field(default=7200)

class AdvancedEndpoint(BaseModel):
    """Advanced PJSIP Endpoint with all configuration options"""
    
    # Basic identification
    id: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    type: str = Field(default="endpoint")
    entity_type: str = Field(default="endpoint")
    name: Optional[str] = Field(None, max_length=100, description="Display name for endpoint")
    
    # Account and billing
    accountcode: Optional[str] = Field(None, max_length=20)
    
    # Audio and media settings
    max_audio_streams: int = Field(default=2, ge=1, le=10)
    device_state_busy_at: int = Field(default=2, ge=1, le=10)
    allow_transfer: str = Field(default="yes", pattern=r'^(yes|no)$')
    
    # Authentication
    outbound_auth: Optional[str] = Field(default="")
    auth: AuthConfig
    
    # Context and routing
    context: str = Field(default="internal", pattern=r'^[a-zA-Z0-9_-]+$')
    
    # Caller ID settings
    callerid: Optional[str] = Field(None, max_length=100)
    callerid_privacy: Optional[str] = Field(default="")
    connected_line_method: str = Field(default="invite")
    from_user: Optional[str] = Field(None, max_length=50)
    from_domain: Optional[str] = Field(default="")
    
    # Transport and network
    transport: str = Field(default="transport-udp")
    identify_by: str = Field(default="username")
    deny: Optional[str] = Field(default="")
    permit: Optional[str] = Field(default="")
    force_rport: str = Field(default="yes", pattern=r'^(yes|no)$')
    rewrite_contact: str = Field(default="yes", pattern=r'^(yes|no)$')
    
    # Codec settings
    allow: str = Field(default="ulaw,alaw")
    disallow: str = Field(default="all")
    
    # WebRTC settings
    webrtc: str = Field(default="no", pattern=r'^(yes|no)$')
    ice_support: str = Field(default="no", pattern=r'^(yes|no)$')
    
    # Music on hold
    moh_suggest: str = Field(default="default")
    
    # Call groups
    call_group: Optional[str] = Field(default="1")
    pickup_group: Optional[str] = Field(default="1")
    
    # RTP settings
    rtp_symmetric: str = Field(default="yes", pattern=r'^(yes|no)$')
    rtp_timeout: int = Field(default=30, ge=0, le=300)
    rtp_timeout_hold: int = Field(default=60, ge=0, le=3600)
    direct_media: str = Field(default="no", pattern=r'^(yes|no)$')
    
    # Recording settings
    one_touch_recording: str = Field(default="yes", pattern=r'^(yes|no)$')
    record_on_feature: str = Field(default="*1")
    record_off_feature: str = Field(default="*2")
    record_calls: str = Field(default="yes", pattern=r'^(yes|no)$')
    
    # Voicemail settings
    mailboxes: Optional[str] = Field(default="")
    voicemail_extension: Optional[str] = Field(default="")
    
    # Subscription and presence
    allow_subscribe: str = Field(default="yes", pattern=r'^(yes|no)$')
    
    # DTMF and signaling
    dtmf_mode: str = Field(default="rfc4733")
    rel100: str = Field(default="no", pattern=r'^(yes|no)$', alias="100rel")
    
    # SDP settings
    sdp_session: str = Field(default="Asterisk")
    
    # Variables and custom settings
    set_var: Optional[str] = Field(default="")
    tone_zone: str = Field(default="us")
    
    # Privacy and identification
    send_pai: str = Field(default="yes", pattern=r'^(yes|no)$')
    send_rpid: str = Field(default="yes", pattern=r'^(yes|no)$')
    
    # Hardware and provisioning
    mac_address: Optional[str] = Field(None, pattern=r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    auto_provisioning_enabled: bool = Field(default=True)
    
    # AOR configuration
    aor: AORConfig
    
    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True

    @field_validator('allow')
    @classmethod
    def validate_codecs(cls, v):
        if not v or v == "all":
            return v
        allowed_codecs = ['ulaw', 'alaw', 'g722', 'g729', 'gsm', 'opus', 'h264', 'vp8', 'vp9']
        codecs = [codec.strip() for codec in v.split(',')]
        for codec in codecs:
            if codec not in allowed_codecs and codec != "all":
                raise ValueError(f'Invalid codec: {codec}')
        return v

    @field_validator('callerid')
    @classmethod
    def validate_callerid(cls, v):
        if v and not re.match(r'^[\w\s<>@.-]+$', v):
            raise ValueError('Invalid caller ID format')
        return v

class SimpleEndpoint(BaseModel):
    """Simplified endpoint for basic operations"""
    id: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    context: str = Field(default="internal")
    codecs: List[str] = Field(default=["ulaw", "alaw"])
    max_contacts: int = Field(default=1, ge=1, le=10)
    callerid: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=100)

    @field_validator('codecs')
    @classmethod
    def validate_codecs(cls, v):
        allowed_codecs = ['ulaw', 'alaw', 'g722', 'g729', 'gsm', 'opus']
        for codec in v:
            if codec not in allowed_codecs:
                raise ValueError(f'Invalid codec: {codec}')
        return v

class EndpointCreate(BaseModel):
    """Create endpoint - can use either simple or advanced format"""
    simple: Optional[SimpleEndpoint] = None
    advanced: Optional[AdvancedEndpoint] = None

    def get_endpoint_data(self) -> Dict[str, Any]:
        """Get endpoint data in unified format"""
        if self.advanced:
            return self.advanced.model_dump()
        elif self.simple:
            # Convert simple to advanced format
            return {
                'id': self.simple.id,
                'name': self.simple.name or f"Extension {self.simple.id}",
                'context': self.simple.context,
                'allow': ','.join(self.simple.codecs),
                'callerid': self.simple.callerid or "",
                'auth': {
                    'username': self.simple.username,
                    'password': self.simple.password,
                    'realm': 'UVLink'
                },
                'aor': {
                    'max_contacts': self.simple.max_contacts
                }
            }
        else:
            raise ValueError("Either simple or advanced endpoint data must be provided")

class EndpointUpdate(BaseModel):
    """Update endpoint configuration"""
    name: Optional[str] = Field(None, max_length=100)
    context: Optional[str] = Field(None, pattern=r'^[a-zA-Z0-9_-]+$')
    callerid: Optional[str] = Field(None, max_length=100)
    allow: Optional[str] = Field(None)
    transport: Optional[str] = Field(None)
    webrtc: Optional[str] = Field(None, pattern=r'^(yes|no)$')
    max_contacts: Optional[int] = Field(None, ge=1, le=10)
    qualify_frequency: Optional[int] = Field(None, ge=0, le=300)
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    realm: Optional[str] = Field(None, max_length=100)

class BulkEndpointCreate(BaseModel):
    """Create multiple endpoints at once"""
    endpoints: List[Union[SimpleEndpoint, AdvancedEndpoint]]
    overwrite_existing: bool = Field(default=False)

# Response models
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
    conflicts: Optional[List[str]] = None

class EndpointListResponse(BaseModel):
    success: bool
    count: int
    endpoints: List[Dict[str, Any]]

# Legacy compatibility
class Endpoint(SimpleEndpoint):
    """Legacy endpoint model for backward compatibility"""
    pass

class EndpointsList(BaseModel):
    """Legacy endpoints list for backward compatibility"""
    endpoints: List[SimpleEndpoint]