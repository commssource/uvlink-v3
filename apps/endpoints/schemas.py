from pydantic import BaseModel, Field, field_validator, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from shared.models import PasswordField
import re

class AudioMediaSettings(BaseModel):
    """Audio and media configuration settings"""
    max_audio_streams: int = Field(default=2, ge=1, le=10)
    allow: str = Field(default="ulaw,alaw")
    disallow: str = Field(default="all")
    moh_suggest: str = Field(default="default")
    tone_zone: str = Field(default="us")
    dtmf_mode: str = Field(default="rfc4733")
    allow_transfer: str = Field(default="yes", pattern=r'^(yes|no)$')

    @field_validator('allow')
    @classmethod
    def validate_codecs(cls, v: str) -> str:
        """Validate codec list"""
        if not v or v == "all":
            return v
        allowed_codecs = ['ulaw', 'alaw', 'g722', 'g729', 'gsm', 'opus', 'h264', 'vp8', 'vp9']
        codecs = [codec.strip() for codec in v.split(',')]
        for codec in codecs:
            if codec not in allowed_codecs and codec != "all":
                raise ValueError(f'Invalid codec: {codec}')
        return v

class TransportNetworkSettings(BaseModel):
    """Transport and network configuration settings"""
    transport: str = Field(default="transport-udp")
    identify_by: str = Field(default="username")
    deny: Optional[str] = Field(default="")
    permit: Optional[str] = Field(default="")
    force_rport: str = Field(default="yes", pattern=r'^(yes|no)$')
    rewrite_contact: str = Field(default="yes", pattern=r'^(yes|no)$')
    from_user: Optional[str] = Field(None, max_length=50)
    from_domain: Optional[str] = Field(default="")
    direct_media: str = Field(default="no", pattern=r'^(yes|no)$')
    ice_support: str = Field(default="no", pattern=r'^(yes|no)$')
    webrtc: str = Field(default="no", pattern=r'^(yes|no)$')

class RTPSettings(BaseModel):
    """RTP configuration settings"""
    rtp_symmetric: str = Field(default="yes", pattern=r'^(yes|no)$')
    rtp_timeout: int = Field(default=30, ge=0, le=300)
    rtp_timeout_hold: int = Field(default=60, ge=0, le=3600)
    sdp_session: str = Field(default="Asterisk")

class RecordingSettings(BaseModel):
    """Recording configuration settings"""
    record_calls: str = Field(default="yes", pattern=r'^(yes|no)$')
    one_touch_recording: str = Field(default="yes", pattern=r'^(yes|no)$')
    record_on_feature: str = Field(default="*1")
    record_off_feature: str = Field(default="*2")

class CallSettings(BaseModel):
    """Call handling configuration settings"""
    context: str = Field(default="internal", pattern=r'^[a-zA-Z0-9_-]+$')
    callerid: Optional[str] = Field(None, max_length=100)
    callerid_privacy: Optional[str] = Field(default="")
    connected_line_method: str = Field(default="invite")
    call_group: Optional[str] = Field(default="1")
    pickup_group: Optional[str] = Field(default="1")
    device_state_busy_at: int = Field(default=2, ge=1, le=10)

    @field_validator('callerid')
    @classmethod
    def validate_callerid(cls, v: Optional[str]) -> Optional[str]:
        """Validate caller ID format"""
        if v and not re.match(r'^[\w\s<>@.-]+$', v):
            raise ValueError('Invalid caller ID format')
        return v

class PresenceSettings(BaseModel):
    """Presence and subscription settings"""
    allow_subscribe: str = Field(default="yes", pattern=r'^(yes|no)$')
    send_pai: str = Field(default="yes", pattern=r'^(yes|no)$')
    send_rpid: str = Field(default="yes", pattern=r'^(yes|no)$')
    rel100: str = Field(default="no", pattern=r'^(yes|no)$', alias="100rel")

class VoicemailSettings(BaseModel):
    """Voicemail configuration settings"""
    mailboxes: Optional[str] = Field(default="")
    voicemail_extension: Optional[str] = Field(default="")

class AuthConfig(BaseModel):
    """Authentication configuration"""
    type: str = Field(default="auth")
    auth_type: str = Field(default="userpass")
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)
    realm: Optional[str] = Field(None, max_length=100)

class AORConfig(BaseModel):
    """Address of Record configuration"""
    type: str = Field(default="aor")
    max_contacts: int = Field(default=2, ge=1, le=10)
    qualify_frequency: Optional[int] = Field(default=60, ge=0, le=300)
    authenticate_qualify: Optional[str] = Field(default="no")
    default_expiration: Optional[int] = Field(default=3600)
    minimum_expiration: Optional[int] = Field(default=60)
    maximum_expiration: Optional[int] = Field(default=7200)

class AdvancedEndpoint(BaseModel):
    """Advanced PJSIP Endpoint with all configuration options organized by category"""
    id: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    type: str = Field(default="endpoint")
    accountcode: Optional[str] = Field(None, max_length=20)
    audio_media: AudioMediaSettings = Field(default_factory=AudioMediaSettings)
    transport_network: TransportNetworkSettings = Field(default_factory=TransportNetworkSettings)
    rtp: RTPSettings = Field(default_factory=RTPSettings)
    recording: RecordingSettings = Field(default_factory=RecordingSettings)
    call: CallSettings = Field(default_factory=CallSettings)
    presence: PresenceSettings = Field(default_factory=PresenceSettings)
    voicemail: VoicemailSettings = Field(default_factory=VoicemailSettings)
    auth: AuthConfig
    aor: AORConfig
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert nested structure to flat dictionary for PJSIP config"""
        flat_dict = {
            'id': self.id,
            'type': self.type,
            'accountcode': self.accountcode,
            'auth': self.auth.model_dump(),
            'aor': self.aor.model_dump()
        }
        for section in [self.audio_media, self.transport_network, self.rtp, 
                        self.recording, self.call, self.presence, self.voicemail]:
            flat_dict.update(section.model_dump())
        return flat_dict

class SimpleEndpoint(BaseModel):
    """Simple endpoint configuration with basic settings"""
    id: str
    username: Optional[str] = None  # Optional since it can be in auth
    password: str  # Required password
    context: str = "internal"
    codecs: List[str] = ["ulaw", "alaw"]
    max_contacts: int = 1
    callerid: Optional[str] = None
    custom_data: Optional[Dict[str, Any]] = None
    auth: Optional[AuthConfig] = None
    aor: Optional[AORConfig] = None

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str], info) -> Optional[str]:
        """Validate username is provided either directly or in auth"""
        values = info.data
        if not v and not values.get('auth', {}).get('username'):
            raise ValueError('username must be provided either directly or in auth object')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str, info) -> str:
        """Validate password is provided"""
        if not v:
            raise ValueError('password must be provided')
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
    context: Optional[str] = Field(None, pattern=r'^[a-zA-Z0-9_-]+$')
    callerid: Optional[str] = Field(None, max_length=100)
    allow: Optional[str] = Field(None)
    transport: Optional[str] = Field(None)
    webrtc: Optional[str] = Field(None, pattern=r'^(yes|no)$')
    max_contacts: Optional[int] = Field(None, ge=1, le=10)
    qualify_frequency: Optional[int] = Field(None, ge=0, le=300)
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    password: Optional[str] = PasswordField(None, min_length=8, max_length=128)
    realm: Optional[str] = Field(None, max_length=100)

class BulkEndpointCreate(BaseModel):
    """Create multiple endpoints at once"""
    endpoints: List[Union[SimpleEndpoint, AdvancedEndpoint]]
    overwrite_existing: bool = Field(default=False)

# Response models
class EndpointListResponse(BaseModel):
    """Response model for listing endpoints with organized sections"""
    success: bool
    count: int
    endpoints: List[Dict[str, Any]]

class StatusResponse(BaseModel):
    """Generic status response"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

class ReloadResponse(BaseModel):
    """Response for reload operations"""
    success: bool
    message: str
    output: Optional[str] = None

class ConfigResponse(BaseModel):
    """Response for configuration operations"""
    success: bool
    config: str
    timestamp: str

class EndpointValidation(BaseModel):
    """Response for endpoint validation"""
    endpoint_id: str
    exists: bool
    available: bool
    conflicts: Optional[List[str]] = None

# Legacy compatibility
class Endpoint(SimpleEndpoint):
    """Legacy endpoint model for backward compatibility"""
    pass

class EndpointsList(BaseModel):
    """Legacy endpoints list for backward compatibility"""
    endpoints: List[SimpleEndpoint]