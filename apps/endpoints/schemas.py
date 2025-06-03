from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
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
    context: str = Field(default="internal")
    disallow: str = Field(default="all")
    accountcode: Optional[str] = Field(None, max_length=20)
    set_var: Optional[str] = Field(default="")
    max_audio_streams: int = Field(default=2)
    device_state_busy_at: int = Field(default=2)
    allow_transfer: str = Field(default="yes")
    outbound_auth: Optional[str] = Field(default="")
    callerid: Optional[str] = Field(None)
    callerid_privacy: Optional[str] = Field(default="")
    connected_line_method: str = Field(default="invite")
    transport_network: Optional[TransportNetworkSettings] = Field(default_factory=TransportNetworkSettings)
    audio_media: Optional[AudioMediaSettings] = Field(default_factory=AudioMediaSettings)
    identify_by: str = Field(default="username")
    deny: Optional[str] = Field(default="")
    permit: Optional[str] = Field(default="")
    force_rport: str = Field(default="yes")
    webrtc: str = Field(default="no")
    moh_suggest: str = Field(default="default")
    call_group: str = Field(default="1")
    rtp_symmetric: str = Field(default="yes")
    rtp_timeout: int = Field(default=30)
    rtp_timeout_hold: int = Field(default=60)
    rewrite_contact: str = Field(default="yes")
    from_user: Optional[str] = Field(None)
    from_domain: Optional[str] = Field(default="")
    mailboxes: Optional[str] = Field(default="")
    voicemail_extension: Optional[str] = Field(default="")
    pickup_group: str = Field(default="1")
    one_touch_recording: str = Field(default="yes")
    record_on_feature: str = Field(default="*1")
    record_off_feature: str = Field(default="*2")
    record_calls: str = Field(default="yes")
    allow_subscribe: str = Field(default="yes")
    dtmf_mode: str = Field(default="rfc4733")
    rel100: str = Field(default="no", alias="100rel")
    ice_support: str = Field(default="no")
    sdp_session: str = Field(default="Asterisk")
    set_var: Optional[str] = Field(default="")
    tone_zone: str = Field(default="us")
    send_pai: str = Field(default="yes")
    send_rpid: str = Field(default="yes")
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
            'context': self.context,
            'disallow': self.disallow,
            'accountcode': self.accountcode,
            "set_var": self.set_var,
            'max_audio_streams': self.max_audio_streams,
            'device_state_busy_at': self.device_state_busy_at,
            'allow_transfer': self.allow_transfer,
            'outbound_auth': self.outbound_auth,
            'callerid': self.callerid,
            'callerid_privacy': self.callerid_privacy,
            'connected_line_method': self.connected_line_method,
            'identify_by': self.identify_by,
            'deny': self.deny,
            'permit': self.permit,
            'force_rport': self.force_rport,
            'webrtc': self.webrtc,
            'moh_suggest': self.moh_suggest,
            'call_group': self.call_group,
            'rtp_symmetric': self.rtp_symmetric,
            'rtp_timeout': self.rtp_timeout,
            'rtp_timeout_hold': self.rtp_timeout_hold,
            'rewrite_contact': self.rewrite_contact,
            'from_user': self.from_user,
            'from_domain': self.from_domain,
            'mailboxes': self.mailboxes,
            'voicemail_extension': self.voicemail_extension,
            'pickup_group': self.pickup_group,
            'one_touch_recording': self.one_touch_recording,
            'record_on_feature': self.record_on_feature,
            'record_off_feature': self.record_off_feature,
            'record_calls': self.record_calls,
            'allow_subscribe': self.allow_subscribe,
            'dtmf_mode': self.dtmf_mode,
            '100rel': self.rel100,
            'ice_support': self.ice_support,
            'sdp_session': self.sdp_session,
            'set_var': self.set_var,
            'tone_zone': self.tone_zone,
            'send_pai': self.send_pai,
            'send_rpid': self.send_rpid,
            'auth': self.auth.model_dump(),
            'aor': self.aor.model_dump()
        }
        
        # Add transport_network fields
        if self.transport_network:
            flat_dict.update(self.transport_network.model_dump())
            
        # Add audio_media fields
        if self.audio_media:
            flat_dict.update(self.audio_media.model_dump())
            
        return flat_dict

class EndpointUpdate(BaseModel):
    """Update endpoint configuration"""
    id: Optional[str] = Field(None, min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
    type: Optional[str] = Field(None)
    accountcode: Optional[str] = Field(None, max_length=20)
    set_var: Optional[str] = Field(None, max_length=20)
    audio_media: Optional[AudioMediaSettings] = None
    transport_network: Optional[TransportNetworkSettings] = None
    rtp: Optional[RTPSettings] = None
    recording: Optional[RecordingSettings] = None
    call: Optional[CallSettings] = None
    presence: Optional[PresenceSettings] = None
    voicemail: Optional[VoicemailSettings] = None
    auth: Optional[AuthConfig] = None
    aor: Optional[AORConfig] = None

# Response models
class StatusResponse(BaseModel):
    """Generic status response"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

class EndpointListResponse(BaseModel):
    """Response model for listing endpoints"""
    success: bool
    count: int
    endpoints: List[Dict[str, Any]]
    page: int
    limit: int
    total_pages: int

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