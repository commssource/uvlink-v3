from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from . import schemas, services
from shared.database import get_db
from shared.auth.endpoint_auth import EndpointAuth
from typing import Dict, Any

router = APIRouter(prefix="/api/v1/call-centre", tags=["Call Centre Users"])

@router.post("/users", response_model=schemas.CallCentreUserResponse)
async def create_user(
    user: schemas.CallCentreUserCreate,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """Create a new call centre user"""
    service = services.CallCentreUserService(db)
    return await service.create_user(user)

@router.put("/users/{user_id}", response_model=schemas.CallCentreUserResponse)
async def update_user(
    user_id: str,
    user: schemas.CallCentreUserUpdate,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """Update a call centre user"""
    service = services.CallCentreUserService(db)
    return await service.update_user(user_id, user)

@router.delete("/users/{id}")
async def delete_user(
    id: int,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """Delete a call centre user"""
    service = services.CallCentreUserService(db)
    await service.delete_user(id)
    return {"message": "User deleted successfully"}

@router.get("/users", response_model=schemas.PaginatedUserResponse)
async def list_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
    status: Optional[int] = Query(None, description="Filter by status"),
    user_id: Optional[str] = Query(None, description="Filter by user_id"),
    user_name: Optional[str] = Query(None, description="Filter by user_name"),
    email: Optional[str] = Query(None, description="Filter by email"),
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """List all call centre users with pagination and optional filters"""
    service = services.CallCentreUserService(db)
    return await service.list_users(
        skip=skip,
        limit=limit,
        status=status,
        user_id=user_id,
        user_name=user_name,
        email=email
    )

@router.post("/users/{user_id}/login")
async def user_login(
    user_id: str,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """Update user login status"""
    service = services.CallCentreUserService(db)
    return await service.update_login_status(user_id, True)

@router.post("/users/{user_id}/logout")
async def user_logout(
    user_id: str,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """Update user logout status"""
    service = services.CallCentreUserService(db)
    return await service.update_login_status(user_id, False)

@router.get("/users/{id}", response_model=schemas.CallCentreUserResponse)
async def get_user(
    id: int,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """Get a call centre user by ID"""
    service = services.CallCentreUserService(db)
    return await service.get_user_by_id(id)

@router.get("/users/by-user-id/{user_id}", response_model=schemas.CallCentreUserResponse)
async def get_user_by_user_id(
    user_id: str,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """Get a call centre user by their user_id"""
    service = services.CallCentreUserService(db)
    return await service.get_user(user_id)

@router.get("/users/debug/list", response_model=List[schemas.CallCentreUserResponse])
async def debug_list_users(
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(EndpointAuth)
):
    """Debug endpoint to list all users with their IDs"""
    service = services.CallCentreUserService(db)
    return await service.debug_list_users()
