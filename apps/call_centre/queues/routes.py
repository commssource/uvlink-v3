from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from .schemas import QueueConfig, QueueMember, QueueListResponse
from .services import QueueService
from config import ASTERISK_QUEUE_CONFIG

router = APIRouter(
    prefix="/api/v1/queues",
    tags=["queues"]
)

def get_queue_service():
    return QueueService(ASTERISK_QUEUE_CONFIG)

@router.post("/", response_model=bool)
async def create_queue(queue: QueueConfig, service: QueueService = Depends(get_queue_service)):
    """Create a new queue configuration"""
    success = service.create_queue(queue)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create queue")
    return success

@router.get("/{queue_name}", response_model=QueueConfig)
async def get_queue(queue_name: str, service: QueueService = Depends(get_queue_service)):
    """Get queue configuration by name"""
    queue = service.get_queue(queue_name)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue

@router.put("/{queue_name}", response_model=bool)
async def update_queue(queue_name: str, queue: QueueConfig, service: QueueService = Depends(get_queue_service)):
    """Update an existing queue configuration"""
    # Check if the old queue exists
    old_queue = service.get_queue(queue_name)
    if not old_queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    
    # If renaming, check if new name already exists
    if queue_name != queue.name:
        existing_queue = service.get_queue(queue.name)
        if existing_queue:
            raise HTTPException(status_code=400, detail=f"Queue with name {queue.name} already exists")
    
    success = service.update_queue(queue_name, queue)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update queue")
    return success

@router.delete("/{queue_name}", response_model=bool)
async def delete_queue(queue_name: str, service: QueueService = Depends(get_queue_service)):
    """Delete a queue configuration"""
    success = service.delete_queue(queue_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete queue")
    return success

@router.get("/", response_model=QueueListResponse)
async def list_queues(
    service: QueueService = Depends(get_queue_service),
    name: Optional[str] = Query(None, description="Filter by queue name"),
    context: Optional[str] = Query(None, description="Filter by queue context"),
    strategy: Optional[str] = Query(None, description="Filter by queue strategy"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page")
):
    """List all queue configurations with filtering and pagination"""
    return service.list_queues(
        name_filter=name,
        context_filter=context,
        strategy_filter=strategy,
        page=page,
        page_size=page_size
    ) 