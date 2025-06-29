# ============================================================================
# apps/queues/schemas.py - Queue Configuration Schemas
# ============================================================================

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from datetime import datetime


class QueueStrategy(str, Enum):
    """Queue strategy options"""
    RINGALL = "ringall"
    LEASTRECENT = "leastrecent"
    FEWESTCALLS = "fewestcalls"
    RANDOM = "random"
    RRMEMORY = "rrmemory"
    RRORDERED = "rrordered"
    LINEAR = "linear"
    WRANDOM = "wrandom"


class QueueJoinEmpty(str, Enum):
    """Queue join empty options"""
    YES = "yes"
    NO = "no"
    STRICT = "strict"
    LOOSE = "loose"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    WRAPUP = "wrapup"
    PENALTY = "penalty"
    PAUSED = "paused"
    INUSE = "inuse"


class QueueMember(BaseModel):
    """Queue member configuration"""
    interface: str = Field(..., description="Member interface (e.g., PJSIP/1001)")
    penalty: int = Field(default=0, description="Member penalty")
    membername: Optional[str] = Field(None, description="Member name")
    state_interface: Optional[str] = Field(None, description="State interface")
    
    def __str__(self):
        """String representation for config file"""
        parts = [self.interface]
        if self.penalty > 0:
            parts.append(str(self.penalty))
        if self.membername:
            parts.append(self.membername)
        if self.state_interface:
            parts.append(self.state_interface)
        return ",".join(parts)


class QueueConfig(BaseModel):
    """Complete queue configuration"""
    name: str = Field(..., description="Queue name")
    template: str = Field(default="queue-basic", description="Template to use")
    
    # Basic queue settings
    strategy: QueueStrategy = Field(default=QueueStrategy.RINGALL, description="Ring strategy")
    musiconhold: str = Field(default="default", description="Music on hold class")
    timeout: int = Field(default=15, description="Ring timeout in seconds")
    retry: int = Field(default=5, description="Retry delay in seconds")
    maxlen: int = Field(default=0, description="Maximum queue length (0 = unlimited)")
    
    # Join/Leave behavior
    joinempty: Union[QueueJoinEmpty, str] = Field(default=QueueJoinEmpty.YES, description="Join when empty")
    leavewhenempty: Union[QueueJoinEmpty, str] = Field(default=QueueJoinEmpty.NO, description="Leave when empty")
    ringinuse: bool = Field(default=False, description="Ring members in use")
    
    # Announcements
    announce_frequency: int = Field(default=0, description="Announcement frequency")
    announce_holdtime: bool = Field(default=False, description="Announce hold time")
    announce_position: bool = Field(default=True, description="Announce position")
    periodic_announce_frequency: int = Field(default=0, description="Periodic announcement frequency")
    
    # Custom announcement files
    announce: Optional[str] = Field(None, description="Custom announcement file")
    periodic_announce: Optional[str] = Field(None, description="Custom periodic announcement")
    context: Optional[str] = Field(None, description="Announcement context")
    
    # Sound files
    queue_youarenext: Optional[str] = Field(None, description="You are next sound")
    queue_thereare: Optional[str] = Field(None, description="There are sound")
    queue_callswaiting: Optional[str] = Field(None, description="Calls waiting sound")
    queue_holdtime: Optional[str] = Field(None, description="Hold time sound")
    queue_minutes: Optional[str] = Field(None, description="Minutes sound")
    queue_seconds: Optional[str] = Field(None, description="Seconds sound")
    queue_thankyou: Optional[str] = Field(None, description="Thank you sound")
    queue_reporthold: Optional[str] = Field(None, description="Report hold sound")
    
    # Agent behavior
    wrapuptime: int = Field(default=0, description="Wrap up time in seconds")
    autopause: bool = Field(default=False, description="Auto pause on failed calls")
    autopausedelay: int = Field(default=0, description="Auto pause delay")
    autofill: bool = Field(default=True, description="Auto fill calls")
    maxwait: Optional[int] = Field(None, description="Maximum wait time")
    
    # Monitoring and recording
    monitor_type: Optional[str] = Field(None, description="Monitor type")
    monitor_format: Optional[str] = Field(None, description="Monitor format")
    monitor_join: Optional[bool] = Field(None, description="Join monitor files")
    
    # Statistics
    servicelevel: int = Field(default=60, description="Service level in seconds")
    weight: int = Field(default=0, description="Queue weight")
    
    # Members
    members: List[Union[QueueMember, str]] = Field(default_factory=list, description="Queue members")
    
    # Additional variables
    variables: Dict[str, Any] = Field(default_factory=dict, description="Additional template variables")
    
    @validator('name')
    def validate_queue_name(cls, v):
        if not v or not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Queue name must be alphanumeric with hyphens/underscores')
        return v
    
    @validator('members', pre=True)
    def validate_members(cls, v):
        """Convert string members to QueueMember objects"""
        if not v:
            return []
        
        result = []
        for member in v:
            if isinstance(member, str):
                # Parse string format: "interface,penalty,name,state_interface"
                parts = member.split(',')
                if len(parts) >= 1:
                    queue_member = QueueMember(
                        interface=parts[0],
                        penalty=int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                        membername=parts[2] if len(parts) > 2 else None,
                        state_interface=parts[3] if len(parts) > 3 else None
                    )
                    result.append(queue_member)
            elif isinstance(member, QueueMember):
                result.append(member)
            elif isinstance(member, dict):
                result.append(QueueMember(**member))
        
        return result


class QueueCreateRequest(BaseModel):
    """Request to create a new queue"""
    name: str = Field(..., description="Queue name")
    template: str = Field(default="queue-basic", description="Template to use")
    strategy: QueueStrategy = Field(default=QueueStrategy.RINGALL)
    musiconhold: str = Field(default="default")
    timeout: int = Field(default=15, ge=1, le=300)
    retry: int = Field(default=5, ge=1, le=60)
    maxlen: int = Field(default=0, ge=0)
    
    # Members as simple strings for API convenience
    members: List[str] = Field(default_factory=list, description="Queue members (PJSIP/1001 format)")
    
    # Additional options
    variables: Dict[str, Any] = Field(default_factory=dict)
    
    def to_queue_config(self) -> QueueConfig:
        """Convert to QueueConfig"""
        return QueueConfig(
            name=self.name,
            template=self.template,
            strategy=self.strategy,
            musiconhold=self.musiconhold,
            timeout=self.timeout,
            retry=self.retry,
            maxlen=self.maxlen,
            members=self.members,
            variables=self.variables
        )


class QueueUpdateRequest(BaseModel):
    """Request to update an existing queue"""
    name: Optional[str] = Field(None, description="New queue name")
    template: Optional[str] = Field(None, description="Template to use")
    strategy: Optional[QueueStrategy] = Field(None)
    musiconhold: Optional[str] = Field(None)
    timeout: Optional[int] = Field(None, ge=1, le=300)
    retry: Optional[int] = Field(None, ge=1, le=60)
    maxlen: Optional[int] = Field(None, ge=0)
    
    # Members
    members: Optional[List[str]] = Field(None, description="Queue members")
    add_members: Optional[List[str]] = Field(None, description="Members to add")
    remove_members: Optional[List[str]] = Field(None, description="Members to remove")
    
    # Additional options
    variables: Optional[Dict[str, Any]] = Field(None)
    
    def apply_to_config(self, current_config: QueueConfig) -> QueueConfig:
        """Apply updates to existing config"""
        # Start with current config
        updated_data = current_config.dict()
        
        # Apply updates
        if self.name is not None:
            updated_data['name'] = self.name
        if self.template is not None:
            updated_data['template'] = self.template
        if self.strategy is not None:
            updated_data['strategy'] = self.strategy
        if self.musiconhold is not None:
            updated_data['musiconhold'] = self.musiconhold
        if self.timeout is not None:
            updated_data['timeout'] = self.timeout
        if self.retry is not None:
            updated_data['retry'] = self.retry
        if self.maxlen is not None:
            updated_data['maxlen'] = self.maxlen
        
        # Handle members
        if self.members is not None:
            updated_data['members'] = self.members
        else:
            # Handle add/remove members
            current_members = [str(m) for m in current_config.members]
            
            if self.add_members:
                for member in self.add_members:
                    if member not in current_members:
                        current_members.append(member)
            
            if self.remove_members:
                for member in self.remove_members:
                    if member in current_members:
                        current_members.remove(member)
            
            updated_data['members'] = current_members
        
        # Handle variables
        if self.variables is not None:
            updated_data['variables'].update(self.variables)
        
        return QueueConfig(**updated_data)


class QueueResponse(BaseModel):
    """Queue response with metadata"""
    name: str
    template: str
    strategy: str
    musiconhold: str
    timeout: int
    retry: int
    maxlen: int
    member_count: int
    members: List[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QueueListResponse(BaseModel):
    """Response for listing queues"""
    queues: List[QueueResponse]
    total_count: int
    page: int = 1
    page_size: int = 50
    total_pages: int

# Example schemas you'll need in apps/queues/schemas.py
class StructuredQueue(BaseModel):
    name: str
    strategy: str
    members: List[QueueMember]
    enabled: bool
    musiconhold: Optional[str]
    timeout: int
    retry: int
    maxlen: int
    member_count: int
    members: List[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # ... other queue properties

class QueueFilters(BaseModel):
    name: Optional[str] = None
    strategy: Optional[str] = None
    status: Optional[str] = None

class QueueSortOptions(str, Enum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    # ... other sort options

class QueueStatistics(BaseModel):
    name: str
    status: str
    member_count: int
    longest_call: Optional[int] = None
    shortest_call: Optional[int] = None
    average_call_duration: Optional[int] = None
    service_level: Optional[int] = None
    service_level_95: Optional[int] = None
    service_level_99: Optional[int] = None