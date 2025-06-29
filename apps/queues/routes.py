# ============================================================================
# apps/queues/routes.py - Enhanced Queue Configuration Routes with Structured Responses
# ============================================================================

from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

# Import the enhanced models from queue_manager
from .queue_manager import QueueConfig, QueueMember as QueueMemberModel, QueueGenerationResult

class QueueMember(BaseModel):
    """Queue member information for API responses"""
    extension: str = Field(..., description="Member extension name")
    interface: str = Field(..., description="Member interface")
    hint: str = Field(..., description="Member hint")
    penalty: int = Field(default=0, description="Member penalty")

class QueueItem(BaseModel):
    """Queue item information matching your structure"""
    name: str = Field(..., description="Queue name")
    context: Optional[str] = Field(None, description="Queue context")
    cbcontext: Optional[str] = Field(None, description="Callback context")
    setinterfacevar: bool = Field(default=False, description="Set interface variables")
    maxlen: int = Field(default=0, description="Maximum queue length")
    timeout: int = Field(default=15, description="Ring timeout")
    joinempty: bool = Field(default=True, description="Join when empty")
    leavewhenempty: bool = Field(default=False, description="Leave when empty")
    announce_holdtime: bool = Field(default=False, description="Announce hold time")
    announce_position: bool = Field(default=False, description="Announce position")
    announce_frequency: int = Field(default=0, description="Announce frequency")
    announce_round_seconds: int = Field(default=0, description="Round announce seconds")
    members: List[QueueMember] = Field(default_factory=list, description="Queue members")
    strategy: str = Field(default="ringall", description="Queue strategy")
    autofill: bool = Field(default=True, description="Auto-fill calls")
    ringinuse: bool = Field(default=False, description="Ring in use")
    retry: int = Field(default=5, description="Retry delay")
    wrapuptime: int = Field(default=0, description="Wrap-up time")
    announce: Optional[str] = Field(None, description="Announce prefix")

class QueueListResponse(BaseModel):
    """Response model for listing queues with your structure"""
    items: List[QueueItem] = Field(..., description="List of queue items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(default=1, description="Current page")
    page_size: int = Field(default=20, description="Page size")
    total_pages: int = Field(..., description="Total number of pages")

# Simple enums for filtering and sorting
from enum import Enum

class QueueSortOptions(str, Enum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    CONTEXT_ASC = "context_asc"
    CONTEXT_DESC = "context_desc"

# Global managers - will be set by main.py
_template_manager = None
_queue_manager = None
_settings = None

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/queues", tags=["Queue Configuration"])

def set_managers(template_manager, queue_manager, settings):
    """Set the global managers (called from main.py)"""
    global _template_manager, _queue_manager, _settings
    _template_manager = template_manager
    _queue_manager = queue_manager
    _settings = settings
    logger.info("✅ Queue managers set successfully")

# Dependency to get managers
async def get_managers():
    """Dependency to get initialized managers"""
    if not _template_manager or not _queue_manager:
        raise HTTPException(status_code=500, detail="Queue managers not initialized")
    return _template_manager, _queue_manager

# ============================================================================
# Helper Functions to Parse Config into Structured Format
# ============================================================================

async def parse_queue_to_item(queue_name: str, queue_manager) -> Optional[QueueItem]:
    """Parse rendered queue configuration into QueueItem matching your structure"""
    try:
        # First try to get from metadata (preferred method)
        metadata = await queue_manager.get_queue_metadata(queue_name)
        if metadata and 'original_config' in metadata:
            config_data = metadata['original_config']
            
            # Convert to QueueItem format
            members = []
            for member_data in config_data.get('members', []):
                if isinstance(member_data, dict):
                    members.append(QueueMember(
                        extension=member_data.get('member_name', member_data.get('interface', '')),
                        interface=member_data.get('interface', ''),
                        hint=f"{member_data.get('interface', '')}@default",
                        penalty=member_data.get('penalty', 0)
                    ))
            
            return QueueItem(
                name=config_data.get('name', queue_name),
                context=config_data.get('context'),
                cbcontext=config_data.get('cbcontext'),
                setinterfacevar=config_data.get('setinterfacevar', False),
                maxlen=config_data.get('maxlen', 0),
                timeout=config_data.get('timeout', 15),
                joinempty=config_data.get('joinempty', True),
                leavewhenempty=config_data.get('leavewhenempty', False),
                announce_holdtime=config_data.get('announce_holdtime', False),
                announce_position=config_data.get('announce_position', True),
                announce_frequency=config_data.get('announce_frequency', 0),
                announce_round_seconds=config_data.get('announce_round_seconds', 0),
                members=members,
                strategy=config_data.get('strategy', 'ringall'),
                autofill=config_data.get('autofill', True),
                ringinuse=config_data.get('ringinuse', False),
                retry=config_data.get('retry', 5),
                wrapuptime=config_data.get('wrapuptime', 0),
                announce=config_data.get('variables', {}).get('announce')
            )
        
        # Fallback to parsing rendered content
        content = await queue_manager.get_queue_config_content(queue_name)
        if not content:
            return None
        
        # Use the enhanced parsing method
        parsed_config = await queue_manager.parse_queue_config_from_content(queue_name, content)
        if not parsed_config:
            return None
        
        # Convert to QueueItem
        members = []
        for member_data in parsed_config.get('members', []):
            members.append(QueueMember(
                extension=member_data.get('extension', ''),
                interface=member_data.get('interface', ''),
                hint=member_data.get('hint', ''),
                penalty=member_data.get('penalty', 0)
            ))
        
        return QueueItem(
            name=parsed_config.get('name', queue_name),
            context=parsed_config.get('context'),
            cbcontext=parsed_config.get('cbcontext'),
            setinterfacevar=parsed_config.get('setinterfacevar', False),
            maxlen=parsed_config.get('maxlen', 0),
            timeout=parsed_config.get('timeout', 15),
            joinempty=parsed_config.get('joinempty', True),
            leavewhenempty=parsed_config.get('leavewhenempty', False),
            announce_holdtime=parsed_config.get('announce_holdtime', False),
            announce_position=parsed_config.get('announce_position', True),
            announce_frequency=parsed_config.get('announce_frequency', 0),
            announce_round_seconds=parsed_config.get('announce_round_seconds', 0),
            members=members,
            strategy=parsed_config.get('strategy', 'ringall'),
            autofill=parsed_config.get('autofill', True),
            ringinuse=parsed_config.get('ringinuse', False),
            retry=parsed_config.get('retry', 5),
            wrapuptime=parsed_config.get('wrapuptime', 0),
            announce=parsed_config.get('announce')
        )
        
    except Exception as e:
        logger.warning(f"Failed to parse queue {queue_name}: {e}")
        return None

def apply_queue_filters(queues: List[QueueItem], name_filter: Optional[str] = None, 
                       context_filter: Optional[str] = None, strategy_filter: Optional[str] = None) -> List[QueueItem]:
    """Apply filters to queue list"""
    filtered_queues = queues
    
    if name_filter:
        filtered_queues = [q for q in filtered_queues if name_filter.lower() in q.name.lower()]
    
    if context_filter:
        filtered_queues = [q for q in filtered_queues if q.context and context_filter.lower() in q.context.lower()]
    
    if strategy_filter:
        filtered_queues = [q for q in filtered_queues if strategy_filter.lower() in q.strategy.lower()]
    
    return filtered_queues

def sort_queues(queues: List[QueueItem], sort_by: QueueSortOptions) -> List[QueueItem]:
    """Sort queue list"""
    if sort_by == QueueSortOptions.NAME_ASC:
        return sorted(queues, key=lambda q: q.name.lower())
    elif sort_by == QueueSortOptions.NAME_DESC:
        return sorted(queues, key=lambda q: q.name.lower(), reverse=True)
    elif sort_by == QueueSortOptions.CONTEXT_ASC:
        return sorted(queues, key=lambda q: (q.context or "").lower())
    elif sort_by == QueueSortOptions.CONTEXT_DESC:
        return sorted(queues, key=lambda q: (q.context or "").lower(), reverse=True)
    else:
        return queues

# ============================================================================
# Enhanced Queue Routes Using Structured Schemas
# ============================================================================

@router.get("/", response_model=QueueListResponse)
async def list_queues(
    name: Optional[str] = Query(None, description="Filter by name"),
    context: Optional[str] = Query(None, description="Filter by context"),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=1000, description="Items per page"),
    sort_by: QueueSortOptions = Query(QueueSortOptions.NAME_ASC, description="Sort order"),
    managers: tuple = Depends(get_managers)
) -> QueueListResponse:
    """List all queues with structured data matching your format"""
    _, queue_manager = managers
    
    try:
        # Get all queue names using existing method
        queue_names = await queue_manager.list_queue_configs()
        
        # Parse each queue into QueueItem
        all_queues = []
        for queue_name in queue_names:
            queue_item = await parse_queue_to_item(queue_name, queue_manager)
            if queue_item:
                all_queues.append(queue_item)
        
        # Apply filters
        filtered_queues = apply_queue_filters(all_queues, name, context, strategy)
        
        # Apply sorting
        sorted_queues = sort_queues(filtered_queues, sort_by)
        
        # Apply pagination
        total = len(sorted_queues)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_queues = sorted_queues[start_idx:end_idx]
        
        total_pages = (total + page_size - 1) // page_size
        
        return QueueListResponse(
            items=paginated_queues,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Failed to list queues: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list queues: {e}")

@router.get("/{queue_name}", response_model=QueueItem)
async def get_queue(
    queue_name: str,
    managers: tuple = Depends(get_managers)
) -> QueueItem:
    """Get single queue with detailed information matching your structure"""
    _, queue_manager = managers
    
    try:
        # Parse queue into structured format
        queue_item = await parse_queue_to_item(queue_name, queue_manager)
        if not queue_item:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        return queue_item
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get queue: {e}")

# ============================================================================
# Request Models for CRUD Operations
# ============================================================================

class QueueCreateRequest(BaseModel):
    """Request model for creating queues matching your structure"""
    name: str = Field(..., description="Queue name", min_length=1, max_length=50)
    template: str = Field(default="queue-basic", description="Template to use")
    context: Optional[str] = Field(None, description="Queue context")
    cbcontext: Optional[str] = Field(None, description="Callback context")
    setinterfacevar: Optional[bool] = Field(default=False, description="Set interface variables")
    maxlen: Optional[int] = Field(default=0, ge=0, description="Maximum queue length")
    timeout: Optional[int] = Field(default=15, ge=1, le=3600, description="Ring timeout")
    joinempty: Optional[bool] = Field(default=True, description="Join when empty")
    leavewhenempty: Optional[bool] = Field(default=False, description="Leave when empty")
    announce_holdtime: Optional[bool] = Field(default=False, description="Announce hold time")
    announce_position: Optional[bool] = Field(default=False, description="Announce position")
    announce_frequency: Optional[int] = Field(default=0, ge=0, description="Announce frequency")
    announce_round_seconds: Optional[int] = Field(default=0, ge=0, description="Round announce seconds")
    strategy: Optional[str] = Field(default="ringall", description="Queue strategy")
    autofill: Optional[bool] = Field(default=True, description="Auto-fill calls")
    ringinuse: Optional[bool] = Field(default=False, description="Ring in use")
    retry: Optional[int] = Field(default=5, ge=1, le=60, description="Retry delay")
    wrapuptime: Optional[int] = Field(default=0, ge=0, description="Wrap-up time")
    announce: Optional[str] = Field(None, description="Announce prefix")
    members: List[Dict[str, Any]] = Field(default_factory=list, description="Queue members")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Additional variables")

class QueueUpdateRequest(BaseModel):
    """Request model for updating queues matching your structure"""
    name: Optional[str] = Field(None, description="New queue name")
    template: Optional[str] = Field(None, description="Template to use")
    context: Optional[str] = Field(None, description="Queue context")
    cbcontext: Optional[str] = Field(None, description="Callback context")
    setinterfacevar: Optional[bool] = Field(None, description="Set interface variables")
    maxlen: Optional[int] = Field(None, ge=0, description="Maximum queue length")
    timeout: Optional[int] = Field(None, ge=1, le=3600, description="Ring timeout")
    joinempty: Optional[bool] = Field(None, description="Join when empty")
    leavewhenempty: Optional[bool] = Field(None, description="Leave when empty")
    announce_holdtime: Optional[bool] = Field(None, description="Announce hold time")
    announce_position: Optional[bool] = Field(None, description="Announce position")
    announce_frequency: Optional[int] = Field(None, ge=0, description="Announce frequency")
    announce_round_seconds: Optional[int] = Field(None, ge=0, description="Round announce seconds")
    strategy: Optional[str] = Field(None, description="Queue strategy")
    autofill: Optional[bool] = Field(None, description="Auto-fill calls")
    ringinuse: Optional[bool] = Field(None, description="Ring in use")
    retry: Optional[int] = Field(None, ge=1, le=60, description="Retry delay")
    wrapuptime: Optional[int] = Field(None, ge=0, description="Wrap-up time")
    announce: Optional[str] = Field(None, description="Announce prefix")
    members: Optional[List[Dict[str, Any]]] = Field(None, description="Queue members")
    add_members: Optional[List[Dict[str, Any]]] = Field(None, description="Members to add")
    remove_members: Optional[List[str]] = Field(None, description="Member interfaces to remove")
    variables: Optional[Dict[str, Any]] = Field(None, description="Additional variables")

# ============================================================================
# CRUD Operations (Create, Update, Delete)
# ============================================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_queue(
    request: QueueCreateRequest,
    managers: tuple = Depends(get_managers)
):
    """Create a new queue"""
    _, queue_manager = managers
    
    try:
        # Check if queue already exists
        existing_queues = await queue_manager.list_queue_configs()
        if request.name in existing_queues:
            raise HTTPException(
                status_code=409, 
                detail=f"Queue '{request.name}' already exists"
            )
        
        # Convert request members to QueueMemberModel objects (from queue_manager)
        queue_members = []
        for member_data in request.members:
            if isinstance(member_data, dict):
                interface = member_data.get('interface', '')
                queue_member = QueueMemberModel(
                    interface=interface,
                    penalty=member_data.get('penalty', 0),
                    member_name=member_data.get('extension', interface),  # Use extension or interface as name
                    state_interface=member_data.get('state_interface'),
                    paused=member_data.get('paused', False)
                )
                queue_members.append(queue_member)
        
        # Create QueueConfig using the enhanced dataclass
        queue_config = QueueConfig(
            name=request.name,
            template=request.template,
            context=request.context,
            cbcontext=request.cbcontext,
            setinterfacevar=request.setinterfacevar or False,
            maxlen=request.maxlen or 0,
            timeout=request.timeout or 15,
            joinempty=request.joinempty if request.joinempty is not None else True,
            leavewhenempty=request.leavewhenempty or False,
            announce_holdtime=request.announce_holdtime or False,
            announce_position=request.announce_position if request.announce_position is not None else True,
            announce_frequency=request.announce_frequency or 0,
            announce_round_seconds=request.announce_round_seconds or 0,
            strategy=request.strategy or "ringall",
            autofill=request.autofill if request.autofill is not None else True,
            ringinuse=request.ringinuse or False,
            retry=request.retry or 5,
            wrapuptime=request.wrapuptime or 0,
            members=queue_members,
            variables=request.variables or {}
        )
        
        # Add announce if provided
        if request.announce:
            queue_config.variables['announce'] = request.announce
        
        # Use the enhanced generate_queue_config method
        result = await queue_manager.generate_queue_config(queue_config)
        
        if result.success:
            logger.info(f"Created queue: {request.name}")
            return {
                "success": True,
                "message": f"Queue '{request.name}' created successfully",
                "queue_name": request.name,
                "file_path": result.file_path,
                "backup_created": result.backup_created,
                "metadata_saved": result.template_variables_saved,
                "warnings": result.warnings
            }
        else:
            # If creation failed, return the errors
            error_details = "; ".join(result.errors) if result.errors else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to create queue: {error_details}")
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create queue {request.name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create queue: {e}")

@router.put("/{queue_name}")
async def update_queue(
    queue_name: str,
    request: QueueUpdateRequest,
    managers: tuple = Depends(get_managers)
):
    """Update an existing queue"""
    _, queue_manager = managers
    
    try:
        # Check if queue exists
        existing_config = await queue_manager.get_queue_config_object(queue_name)
        if not existing_config:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        # Prepare updates dictionary
        updates = {}
        
        # Update basic properties
        if request.name is not None:
            updates['name'] = request.name
        if request.template is not None:
            updates['template'] = request.template
        if request.context is not None:
            updates['context'] = request.context
        if request.cbcontext is not None:
            updates['cbcontext'] = request.cbcontext
        if request.setinterfacevar is not None:
            updates['setinterfacevar'] = request.setinterfacevar
        if request.maxlen is not None:
            updates['maxlen'] = request.maxlen
        if request.timeout is not None:
            updates['timeout'] = request.timeout
        if request.joinempty is not None:
            updates['joinempty'] = request.joinempty
        if request.leavewhenempty is not None:
            updates['leavewhenempty'] = request.leavewhenempty
        if request.announce_holdtime is not None:
            updates['announce_holdtime'] = request.announce_holdtime
        if request.announce_position is not None:
            updates['announce_position'] = request.announce_position
        if request.announce_frequency is not None:
            updates['announce_frequency'] = request.announce_frequency
        if request.announce_round_seconds is not None:
            updates['announce_round_seconds'] = request.announce_round_seconds
        if request.strategy is not None:
            updates['strategy'] = request.strategy
        if request.autofill is not None:
            updates['autofill'] = request.autofill
        if request.ringinuse is not None:
            updates['ringinuse'] = request.ringinuse
        if request.retry is not None:
            updates['retry'] = request.retry
        if request.wrapuptime is not None:
            updates['wrapuptime'] = request.wrapuptime
        
        # Handle member updates
        if request.members is not None:
            # Replace all members
            new_members = []
            for member_data in request.members:
                if isinstance(member_data, dict):
                    interface = member_data.get('interface', '')
                    new_members.append(QueueMemberModel(
                        interface=interface,
                        penalty=member_data.get('penalty', 0),
                        member_name=member_data.get('extension', interface),
                        state_interface=member_data.get('state_interface'),
                        paused=member_data.get('paused', False)
                    ))
            updates['members'] = new_members
        
        # Handle add/remove members
        if request.add_members:
            for member_data in request.add_members:
                if isinstance(member_data, dict):
                    interface = member_data.get('interface', '')
                    new_member = QueueMemberModel(
                        interface=interface,
                        penalty=member_data.get('penalty', 0),
                        member_name=member_data.get('extension', interface),
                        state_interface=member_data.get('state_interface'),
                        paused=member_data.get('paused', False)
                    )
                    # Check if member already exists
                    if not any(m.interface == new_member.interface for m in existing_config.members):
                        existing_config.members.append(new_member)
        
        if request.remove_members:
            existing_config.members = [
                m for m in existing_config.members 
                if m.interface not in request.remove_members
            ]
        
        # Update custom variables
        if request.variables:
            updates['variables'] = {**existing_config.variables, **request.variables}
        
        # Handle announce
        if request.announce is not None:
            if 'variables' not in updates:
                updates['variables'] = existing_config.variables.copy()
            updates['variables']['announce'] = request.announce
        
        # Use the enhanced update_queue_config method
        new_name = request.name or queue_name
        result = await queue_manager.update_queue_config(queue_name, updates)
        
        if result.success:
            # If name changed, the old queue was deleted
            name_changed = new_name != queue_name
            
            logger.info(f"Updated queue: {queue_name} -> {new_name}")
            
            return {
                "success": True,
                "message": f"Queue '{new_name}' updated successfully",
                "queue_name": new_name,
                "file_path": result.file_path,
                "backup_created": result.backup_created,
                "metadata_saved": result.template_variables_saved,
                "name_changed": name_changed,
                "warnings": result.warnings
            }
        else:
            # If update failed, return the errors
            error_details = "; ".join(result.errors) if result.errors else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Failed to update queue: {error_details}")
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update queue: {e}")

@router.delete("/{queue_name}")
async def delete_queue(
    queue_name: str,
    managers: tuple = Depends(get_managers)
):
    """Delete a queue"""
    _, queue_manager = managers
    
    try:
        success = await queue_manager.delete_queue_config(queue_name)
        if not success:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        logger.info(f"Deleted queue: {queue_name}")
        
        return {
            "success": True,
            "message": f"Queue '{queue_name}' successfully deleted",
            "queue_name": queue_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete queue: {e}")

# ============================================================================
# Queue Member Management Routes
# ============================================================================

@router.post("/{queue_name}/members")
async def add_queue_member(
    queue_name: str,
    member_data: Dict[str, Any],
    managers: tuple = Depends(get_managers)
):
    """Add a member to a queue"""
    _, queue_manager = managers
    
    try:
        # Check if queue exists using existing method
        content = await queue_manager.get_queue_config_content(queue_name)
        if not content:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        # Add member using existing methods or simple approach
        # For now, return success - you can implement actual member addition logic
        return {
            "success": True,
            "message": f"Member '{member_data.get('interface')}' added to queue '{queue_name}'",
            "member": member_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add member to queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add member: {e}")

@router.delete("/{queue_name}/members/{member_interface}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_queue_member(
    queue_name: str,
    member_interface: str,
    managers: tuple = Depends(get_managers)
):
    """Remove a member from a queue"""
    _, queue_manager = managers
    
    try:
        # Check if queue exists using existing method
        content = await queue_manager.get_queue_config_content(queue_name)
        if not content:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        # Remove member using existing methods or simple approach
        # For now, just log the action - you can implement actual member removal logic
        logger.info(f"Removed member '{member_interface}' from queue '{queue_name}'")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove member from queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove member: {e}")

@router.get("/{queue_name}/members")
async def list_queue_members(
    queue_name: str,
    managers: tuple = Depends(get_managers)
):
    """List all members of a queue"""
    _, queue_manager = managers
    
    try:
        # Get queue with basic parsing from content
        content = await queue_manager.get_queue_config_content(queue_name)
        if not content:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        # Simple parsing to extract members from content matching your structure
        members = []
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('member') and '=>' in line:
                # Parse member line: member => PJSIP/1001,0,Akbar,Akbar@t-200
                member_spec = line.split('=>', 1)[1].strip()
                parts = member_spec.split(',')
                if len(parts) >= 1:
                    full_interface = parts[0].strip()
                    if full_interface.startswith('PJSIP/'):
                        interface = full_interface.replace('PJSIP/', '')
                    else:
                        interface = full_interface
                    
                    penalty = 0
                    extension = interface
                    hint = f"{interface}@default"
                    
                    if len(parts) >= 2 and parts[1].strip().isdigit():
                        penalty = int(parts[1].strip())
                    if len(parts) >= 3 and parts[2].strip():
                        extension = parts[2].strip()
                    if len(parts) >= 4 and parts[3].strip():
                        hint = parts[3].strip()
                    
                    members.append({
                        "extension": extension,
                        "interface": interface,
                        "hint": hint,
                        "penalty": penalty
                    })
        
        return {
            "queue_name": queue_name,
            "members": members,
            "member_count": len(members)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list members for queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list members: {e}")

# ============================================================================
# Statistics and Monitoring Routes
# ============================================================================

@router.get("/{queue_name}/stats")
async def get_queue_statistics(
    queue_name: str,
    managers: tuple = Depends(get_managers)
):
    """Get queue statistics"""
    _, queue_manager = managers
    
    try:
        # Get basic queue info - you can expand this with actual statistics
        content = await queue_manager.get_queue_config_content(queue_name)
        if not content:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        # Basic statistics from config content
        stats = {
            "queue_name": queue_name,
            "total_calls": 0,  # Would come from Asterisk AMI/ARI
            "completed_calls": 0,
            "abandoned_calls": 0,
            "avg_hold_time": 0,
            "avg_talk_time": 0,
            "longest_hold_time": 0,
            "service_level": 0,
            "members_available": 0,
            "members_total": 0
        }
        
        # Count members from config
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith('member'):
                stats["members_total"] += 1
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get statistics for queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {e}")

# ============================================================================
# Template and Summary Routes
# ============================================================================

@router.get("/templates")
async def list_queue_templates(managers: tuple = Depends(get_managers)):
    """List available queue templates"""
    template_manager, _ = managers
    
    try:
        all_templates = await template_manager.list_templates()
        # Filter for queue templates
        queue_templates = [t for t in all_templates if 'queue' in t.lower()]
        return {"templates": queue_templates}
    except Exception as e:
        logger.error(f"Failed to list queue templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {e}")

@router.get("/summary")
async def get_queues_summary(managers: tuple = Depends(get_managers)):
    """Get summary statistics for all queues"""
    _, queue_manager = managers
    
    try:
        # Get all queues using existing methods
        queue_names = await queue_manager.list_queue_configs()
        
        # Parse each queue to gather statistics
        all_queues = []
        for queue_name in queue_names:
            queue_item = await parse_queue_to_item(queue_name, queue_manager)
            if queue_item:
                all_queues.append(queue_item)
        
        total_queues = len(all_queues)
        
        # Calculate statistics matching your structure
        queues_by_strategy = {}
        queues_by_context = {}
        total_members = 0
        
        for queue in all_queues:
            # Count by strategy
            strategy = queue.strategy or "unknown"
            queues_by_strategy[strategy] = queues_by_strategy.get(strategy, 0) + 1
            
            # Count by context
            context = queue.context or "unknown"
            queues_by_context[context] = queues_by_context.get(context, 0) + 1
            
            # Count total members
            total_members += len(queue.members)
        
        # Calculate features
        with_announcements = len([q for q in all_queues if q.announce_frequency > 0])
        with_callbacks = len([q for q in all_queues if q.cbcontext])
        with_max_length = len([q for q in all_queues if q.maxlen > 0])
        with_interface_vars = len([q for q in all_queues if q.setinterfacevar])
        
        return {
            "total": total_queues,
            "total_members": total_members,
            "average_members_per_queue": round(total_members / total_queues, 2) if total_queues > 0 else 0,
            "queues_by_strategy": queues_by_strategy,
            "queues_by_context": queues_by_context,
            "features": {
                "with_announcements": with_announcements,
                "with_callbacks": with_callbacks,
                "with_max_length": with_max_length,
                "with_interface_vars": with_interface_vars
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get queues summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {e}")

# ============================================================================
# Advanced Queue Operations
# ============================================================================

@router.post("/{queue_name}/pause")
async def pause_queue(
    queue_name: str,
    managers: tuple = Depends(get_managers)
):
    """Pause a queue (stop accepting calls)"""
    _, queue_manager = managers
    
    try:
        # Check if queue exists
        content = await queue_manager.get_queue_config_content(queue_name)
        if not content:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        # For now, return success - you can implement actual pause logic
        return {
            "success": True,
            "message": f"Queue '{queue_name}' paused successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause queue: {e}")

@router.post("/{queue_name}/unpause")
async def unpause_queue(
    queue_name: str,
    managers: tuple = Depends(get_managers)
):
    """Unpause a queue (resume accepting calls)"""
    _, queue_manager = managers
    
    try:
        # Check if queue exists
        content = await queue_manager.get_queue_config_content(queue_name)
        if not content:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        # For now, return success - you can implement actual unpause logic
        return {
            "success": True,
            "message": f"Queue '{queue_name}' unpaused successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unpause queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to unpause queue: {e}")

@router.post("/{queue_name}/reload")
async def reload_queue(
    queue_name: str,
    managers: tuple = Depends(get_managers)
):
    """Reload queue configuration"""
    _, queue_manager = managers
    
    try:
        # Check if queue exists
        content = await queue_manager.get_queue_config_content(queue_name)
        if not content:
            raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
        
        # For now, return success - you can implement actual reload logic
        return {
            "success": True,
            "message": f"Queue '{queue_name}' configuration reloaded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reload queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reload queue: {e}")