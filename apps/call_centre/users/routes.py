from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from . import schemas, services
from shared.database import get_db
from shared.auth.combined_auth import verify_combined_auth
from typing import Dict, Any

router = APIRouter(prefix="/api/v1/call-centre", tags=["Call Centre Users"])

@router.post("/users", response_model=schemas.CallCentreUserResponse)
async def create_user(
    user: schemas.CallCentreUserCreate,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """Create a new call centre user"""
    service = services.CallCentreUserService(db)
    return await service.create_user(user)

@router.put("/users/{user_id}", response_model=schemas.CallCentreUserResponse)
async def update_user(
    user_id: str,
    user: schemas.CallCentreUserUpdate,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """Update a call centre user"""
    service = services.CallCentreUserService(db)
    return await service.update_user(user_id, user)

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """Delete a call centre user"""
    service = services.CallCentreUserService(db)
    await service.delete_user(user_id)
    return {"message": "User deleted successfully"}

@router.get("/users", response_model=List[schemas.CallCentreUserResponse])
async def list_users(
    status: Optional[int] = Query(None, description="Filter by status"),
    user_id: Optional[str] = Query(None, description="Filter by user_id"),
    user_name: Optional[str] = Query(None, description="Filter by user_name"),
    email: Optional[str] = Query(None, description="Filter by email"),
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """List all call centre users with optional filters"""
    service = services.CallCentreUserService(db)
    return await service.list_users(
        status=status,
        user_id=user_id,
        user_name=user_name,
        email=email
    )

@router.post("/users/{user_id}/login")
async def user_login(
    user_id: str,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """Update user login status"""
    service = services.CallCentreUserService(db)
    return await service.update_login_status(user_id, True)

@router.post("/users/{user_id}/logout")
async def user_logout(
    user_id: str,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """Update user logout status"""
    service = services.CallCentreUserService(db)
    return await service.update_login_status(user_id, False)

@router.get("/users/{id}", response_model=schemas.CallCentreUserResponse)
async def get_user(
    id: int,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """Get a call centre user by ID"""
    service = services.CallCentreUserService(db)
    return await service.get_user_by_id(id)

@router.get("/users/by-user-id/{user_id}", response_model=schemas.CallCentreUserResponse)
async def get_user_by_user_id(
    user_id: str,
    db: Session = Depends(get_db),
    auth: Dict[str, Any] = Depends(verify_combined_auth)
):
    """Get a call centre user by their user_id"""
    service = services.CallCentreUserService(db)
    return await service.get_user(user_id)
