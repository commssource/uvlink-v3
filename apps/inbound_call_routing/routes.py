from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from shared.database import get_db
from shared.auth.endpoint_auth import EndpointAuth
from . import models, schemas
from math import ceil

router = APIRouter(
    prefix="/api/v1/inbound-call-routing",
    tags=["inbound-call-routing"]
)

endpoint_auth = EndpointAuth()

@router.post("/", response_model=schemas.InboundCallRouting)
def create_routing(
    routing: schemas.InboundCallRoutingCreate, 
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth)
):
    db_routing = models.InboundCallRouting(**routing.model_dump())
    db.add(db_routing)
    try:
        db.commit()
        db.refresh(db_routing)
        return db_routing
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="DID number already exists")

@router.get("/", response_model=schemas.PaginatedResponse)
def get_routings(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    did_number: Optional[str] = Query(None, description="Filter by DID number"),
    client_name: Optional[str] = Query(None, description="Filter by client name"),
    destination_value: Optional[str] = Query(None, description="Filter by destination value"),
    status: Optional[bool] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth)
):
    # Build the base query
    query = db.query(models.InboundCallRouting)
    
    # Apply filters if provided
    if did_number:
        query = query.filter(models.InboundCallRouting.did_number.ilike(f"%{did_number}%"))
    if client_name:
        query = query.filter(models.InboundCallRouting.client_name.ilike(f"%{client_name}%"))
    if destination_value:
        query = query.filter(models.InboundCallRouting.destination_value.ilike(f"%{destination_value}%"))
    if status is not None:
        query = query.filter(models.InboundCallRouting.status == status)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    pages = ceil(total / size)
    skip = (page - 1) * size
    
    # Get paginated results
    items = query.offset(skip).limit(size).all()
    
    return schemas.PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages
    )

@router.get("/{routing_id}", response_model=schemas.InboundCallRouting)
def get_routing(
    routing_id: int, 
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth)
):
    routing = db.query(models.InboundCallRouting).filter(models.InboundCallRouting.id == routing_id).first()
    if routing is None:
        raise HTTPException(status_code=404, detail="Routing not found")
    return routing

@router.put("/{routing_id}", response_model=schemas.InboundCallRouting)
def update_routing(
    routing_id: int, 
    routing: schemas.InboundCallRoutingUpdate, 
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(endpoint_auth)
):
    db_routing = db.query(models.InboundCallRouting).filter(models.InboundCallRouting.id == routing_id).first()
    if db_routing is None:
        raise HTTPException(status_code=404, detail="Routing not found")
    
    update_data = routing.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_routing, key, value)
    
    try:
        db.commit()
        db.refresh(db_routing)
        return db_routing
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error updating routing") 