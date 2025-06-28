# ============================================================================
# apps/endpoints/schemas.py - PJSIP-specific Pydantic models
# ============================================================================

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from shared.models import BaseConfigModel, TemplateType
from datetime import datetime
from enum import Enum

class TemplateConfig(BaseConfigModel):
    """Template configuration model"""
    name: str = Field(..., description="Template name")
    type: TemplateType = Field(..., description="Template type")
    description: Optional[str] = Field(None, description="Template description")
    parent_template: Optional[str] = Field(None, description="Parent template for inheritance")
    default_values: Dict[str, Any] = Field(default_factory=dict, description="Default values")
    required_variables: List[str] = Field(default_factory=list, description="Required template variables")
    template_content: str = Field(..., description="Jinja2 template content")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Template name must be alphanumeric with hyphens/underscores')
        return v

class EndpointConfig(BaseConfigModel):
    """Complete endpoint configuration with template inheritance"""
    id: str = Field(..., description="Endpoint identifier")
    template: str = Field(..., description="Base template to use")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Template variables")
    overrides: Dict[str, Any] = Field(default_factory=dict, description="Direct option overrides")
    identify_config: Optional[Dict[str, Any]] = None
    registration_config: Optional[Dict[str, Any]] = None
    
    # Optional endpoint-level configurations
    voicemail: Optional[str] = None
    call_group: Optional[str] = None
    pickup_group: Optional[str] = None
    accountcode: Optional[str] = None
    caller_id_privacy: Optional[str] = None
    context: Optional[str] = None
    
    # Nested configurations
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")
    aor_config: Optional[Dict[str, Any]] = Field(None, description="AOR configuration")
    transport_config: Optional[Dict[str, Any]] = Field(None, description="Transport configuration")
    
    @validator('id')
    def validate_endpoint_id(cls, v):
        if not v or not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Endpoint ID must be alphanumeric with hyphens/underscores')
        return v

class TemplateRenderRequest(BaseModel):
    """Request model for template rendering"""
    template_name: str
    variables: Dict[str, Any] = Field(default_factory=dict)

class BulkEndpointRequest(BaseModel):
    """Request model for bulk endpoint creation"""
    endpoints: List[EndpointConfig]
    validate_before_create: bool = True


# ============================================================================
# Enhanced PJSIP Endpoint Models for Structured Responses
# ============================================================================

class AudioMediaConfig(BaseModel):
    """Audio and media configuration"""
    max_audio_streams: int = Field(default=2, description="Maximum audio streams")
    allow: str = Field(default="ulaw,alaw", description="Allowed codecs")
    disallow: str = Field(default="all", description="Disallowed codecs")
    moh_suggest: Optional[str] = Field(default="default", description="Music on hold class")
    tone_zone: str = Field(default="us", description="Tone zone")
    dtmf_mode: str = Field(default="rfc4733", description="DTMF mode")
    allow_transfer: str = Field(default="yes", description="Allow transfers")

class TransportNetworkConfig(BaseModel):
    """Transport and network configuration"""
    transport: Optional[str] = Field(default="udp", description="Transport type")
    identify_by: str = Field(default="username", description="Identification method")
    deny: str = Field(default="", description="Denied IP addresses/networks")
    permit: str = Field(default="", description="Permitted IP addresses/networks")
    force_rport: str = Field(default="yes", description="Force rport")
    rewrite_contact: str = Field(default="yes", description="Rewrite contact header")
    from_user: Optional[str] = Field(default=None, description="From user")
    from_domain: str = Field(default="", description="From domain")
    direct_media: bool = Field(default=False, description="Direct media")
    ice_support: str = Field(default="no", description="ICE support")
    webrtc: str = Field(default="no", description="WebRTC support")

class RTPConfig(BaseModel):
    """RTP configuration"""
    rtp_symmetric: str = Field(default="yes", description="Symmetric RTP")
    rtp_timeout: int = Field(default=30, description="RTP timeout in seconds")
    rtp_timeout_hold: int = Field(default=60, description="RTP timeout on hold")
    sdp_session: str = Field(default="Asterisk", description="SDP session name")

class RecordingConfig(BaseModel):
    """Call recording configuration"""
    record_calls: str = Field(default="no", description="Record calls automatically")
    one_touch_recording: str = Field(default="no", description="One touch recording")
    record_on_feature: str = Field(default="*1", description="Feature code to start recording")
    record_off_feature: str = Field(default="*2", description="Feature code to stop recording")

class CallConfig(BaseModel):
    """Call handling configuration"""
    context: str = Field(default="internal", description="Dialplan context")
    callerid: Optional[str] = Field(default=None, description="Caller ID")
    callerid_privacy: str = Field(default="", description="Caller ID privacy")
    connected_line_method: str = Field(default="invite", description="Connected line method")
    call_group: Optional[str] = Field(default=None, description="Call group")
    pickup_group: Optional[str] = Field(default=None, description="Pickup group")
    device_state_busy_at: int = Field(default=1, description="Device busy at N calls")

class PresenceConfig(BaseModel):
    """Presence and subscription configuration"""
    allow_subscribe: str = Field(default="yes", description="Allow subscriptions")
    send_pai: str = Field(default="yes", description="Send P-Asserted-Identity")
    send_rpid: str = Field(default="yes", description="Send Remote-Party-ID")
    rel100: str = Field(default="no", description="100rel support")

class VoicemailConfig(BaseModel):
    """Voicemail configuration"""
    mailboxes: str = Field(default="", description="Voicemail mailboxes")
    voicemail_extension: str = Field(default="", description="Voicemail extension")

class AuthConfig(BaseModel):
    """Authentication configuration"""
    type: str = Field(default="auth", description="Section type")
    auth_type: str = Field(default="userpass", description="Authentication type")
    username: str = Field(..., description="Authentication username")
    password: str = Field(..., description="Authentication password")
    realm: str = Field(default="", description="Authentication realm")

class AORConfig(BaseModel):
    """Address of Record configuration"""
    type: str = Field(default="aor", description="Section type")
    remove_existing: str = Field(default="yes", description="Remove existing")
    max_contacts: int = Field(default=1, description="Maximum contacts")
    qualify_timeout: int = Field(default=3, description="Qualify timeout")
    qualify_frequency: int = Field(default=60, description="Qualify frequency")
    authenticate_qualify: str = Field(default="no", description="Authenticate qualify")
    default_expiration: int = Field(default=3600, description="Default expiration")
    minimum_expiration: int = Field(default=60, description="Minimum expiration")
    maximum_expiration: int = Field(default=7200, description="Maximum expiration")

class StructuredEndpoint(BaseModel):
    """Complete structured endpoint representation"""
    id: str = Field(..., description="Endpoint identifier")
    type: str = Field(default="endpoint", description="Object type")
    accountcode: Optional[str] = Field(default=None, description="Account code")
    set_var: str = Field(default="", description="Channel variables")
    
    # Grouped configurations
    audio_media: AudioMediaConfig = Field(default_factory=AudioMediaConfig)
    transport_network: TransportNetworkConfig = Field(default_factory=TransportNetworkConfig)
    rtp: RTPConfig = Field(default_factory=RTPConfig)
    recording: RecordingConfig = Field(default_factory=RecordingConfig)
    call: CallConfig = Field(default_factory=CallConfig)
    presence: PresenceConfig = Field(default_factory=PresenceConfig)
    voicemail: VoicemailConfig = Field(default_factory=VoicemailConfig)
    auth: AuthConfig = Field(..., description="Authentication configuration")
    aor: AORConfig = Field(..., description="AOR configuration")
    
    # Metadata
    template_used: Optional[str] = Field(default=None, description="Template used to create")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

class EndpointListResponse(BaseModel):
    """Response for listing endpoints"""
    endpoints: List[StructuredEndpoint] = Field(..., description="List of endpoints")
    total_count: int = Field(..., description="Total number of endpoints")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=50, description="Page size")

# ============================================================================
# Enhanced Filtering Models
# ============================================================================

class EndpointTypeFilter(str, Enum):
    """Endpoint type filter options"""
    ENDPOINT = "endpoint"
    TRUNK = "trunk"
    WEBRTC = "webrtc"
    CONFERENCE = "conference"
    ALL = "all"

class AuthTypeFilter(str, Enum):
    """Authentication type filter options"""
    USERPASS = "userpass"
    MD5 = "md5"
    OAUTH = "oauth"
    ALL = "all"

class EndpointFilters(BaseModel):
    """Comprehensive endpoint filtering parameters"""
    id: Optional[str] = Field(None, description="Filter by endpoint ID (partial match)")
    ids: Optional[List[str]] = Field(None, description="Filter by specific endpoint IDs")
    type: Optional[EndpointTypeFilter] = Field(EndpointTypeFilter.ALL, description="Filter by endpoint type")
    username: Optional[str] = Field(None, description="Filter by authentication username (partial match)")
    auth_type: Optional[AuthTypeFilter] = Field(AuthTypeFilter.ALL, description="Filter by authentication type")
    context: Optional[str] = Field(None, description="Filter by dialplan context")
    accountcode: Optional[str] = Field(None, description="Filter by account code")
    transport: Optional[str] = Field(None, description="Filter by transport type")
    callerid: Optional[str] = Field(None, description="Filter by caller ID (partial match)")
    template_used: Optional[str] = Field(None, description="Filter by template used")
    max_contacts_gte: Optional[int] = Field(None, description="Filter by max contacts >= value")
    max_contacts_lte: Optional[int] = Field(None, description="Filter by max contacts <= value")
    direct_media: Optional[bool] = Field(None, description="Filter by direct media setting")
    webrtc_enabled: Optional[bool] = Field(None, description="Filter by WebRTC support")
    recording_enabled: Optional[bool] = Field(None, description="Filter by call recording enabled")
    created_after: Optional[str] = Field(None, description="Filter by creation date (ISO format)")
    created_before: Optional[str] = Field(None, description="Filter by creation date (ISO format)")

class SortOptions(str, Enum):
    """Sorting options"""
    ID_ASC = "id_asc"
    ID_DESC = "id_desc"
    USERNAME_ASC = "username_asc"
    USERNAME_DESC = "username_desc"
    CREATED_ASC = "created_asc"
    CREATED_DESC = "created_desc"
    CONTEXT_ASC = "context_asc"
    CONTEXT_DESC = "context_desc"

class EndpointListResponse(BaseModel):
    """Enhanced response for listing endpoints with metadata"""
    endpoints: List[StructuredEndpoint] = Field(..., description="List of endpoints")
    total_count: int = Field(..., description="Total number of endpoints (before pagination)")
    filtered_count: int = Field(..., description="Number of endpoints after filtering")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")
    total_pages: int = Field(..., description="Total number of pages")
    filters_applied: Dict[str, Any] = Field(..., description="Applied filters")
    sort_by: str = Field(..., description="Sort criteria")


class EndpointCreateRequest(BaseModel):
    """Request model for creating endpoints and trunks"""
    id: str = Field(..., description="Unique identifier", min_length=1, max_length=50)
    template: str = Field(..., description="Template to use")
    context: Optional[str] = Field("internal", description="Dialplan context")
    callerid: Optional[str] = Field(None, description="Caller ID")
    accountcode: Optional[str] = Field(None, description="Account code")
    password: Optional[str] = Field(None, description="Password")
    transport: Optional[str] = Field("transport-udp", description="Transport")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Additional variables")
    
    # Remove duplicate fields - you had auth_config, aor_config, transport_config twice
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Auth configuration")
    aor_config: Optional[Dict[str, Any]] = Field(None, description="AOR configuration")
    transport_config: Optional[Dict[str, Any]] = Field(None, description="Transport configuration")
    identify_config: Optional[Dict[str, Any]] = Field(None, description="Identify configuration")
    registration_config: Optional[Dict[str, Any]] = Field(None, description="Registration configuration")

    def to_endpoint_config(self) -> EndpointConfig:
        """Convert to EndpointConfig schema model"""
        return EndpointConfig(
            id=self.id,
            template=self.template,
            variables={
                "context": self.context,
                "callerid": self.callerid,
                "accountcode": self.accountcode,
                "password": self.password,
                "transport": self.transport,
                **self.variables
            },
            auth_config=self.auth_config,
            aor_config=self.aor_config,
            transport_config=self.transport_config,
            identify_config=self.identify_config,  # Add these fields
            registration_config=self.registration_config  # Add these fields
        )

class EndpointUpdateRequest(BaseModel):
    """Request model for updating endpoints and trunks"""
    id: Optional[str] = Field(None, description="New ID (if changing)")
    template: Optional[str] = Field(None, description="Template")
    context: Optional[str] = Field(None, description="Context")
    callerid: Optional[str] = Field(None, description="Caller ID")
    accountcode: Optional[str] = Field(None, description="Account code")
    password: Optional[str] = Field(None, description="Password")
    transport: Optional[str] = Field(None, description="Transport")
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Auth config")
    aor_config: Optional[Dict[str, Any]] = Field(None, description="AOR config")
    transport_config: Optional[Dict[str, Any]] = Field(None, description="Transport config")
    identify_config: Optional[Dict[str, Any]] = Field(None, description="Identify configuration")
    registration_config: Optional[Dict[str, Any]] = Field(None, description="Registration configuration")

    def to_endpoint_config(self, endpoint_id: str, current_template: str = "endpoint-basic") -> EndpointConfig:
        """Convert to EndpointConfig schema model with proper parameter handling"""
        variables = {}
        
        # Only add variables that are not None
        if self.context is not None:
            variables["context"] = self.context
        if self.callerid is not None:
            variables["callerid"] = self.callerid
        if self.accountcode is not None:
            variables["accountcode"] = self.accountcode
        if self.password is not None:
            variables["password"] = self.password
        if self.transport is not None:
            variables["transport"] = self.transport
        if self.variables:
            variables.update(self.variables)

        return EndpointConfig(
            id=self.id or endpoint_id,
            template=self.template or current_template,
            variables=variables,
            auth_config=self.auth_config,
            aor_config=self.aor_config,
            transport_config=self.transport_config,
            identify_config=self.identify_config,  # Add these fields
            registration_config=self.registration_config  # Add these fields
        )
