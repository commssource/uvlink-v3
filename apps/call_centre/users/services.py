from fastapi import HTTPException
from sqlalchemy.orm import Session
from . import models, schemas
from typing import List, Optional, Union
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CallCentreUserService:
    def __init__(self, db: Session):
        self.db = db

    async def create_user(self, user: schemas.CallCentreUserCreate) -> schemas.CallCentreUserResponse:
        """Create a new call centre user"""
        try:
            # Check if user_id already exists
            existing_user = self.db.query(models.CallCentreUser).filter(
                models.CallCentreUser.user_id == user.user_id
            ).first()
            
            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail=f"User with ID {user.user_id} already exists"
                )
            
            # Create new user
            db_user = models.CallCentreUser(
                user_name=user.user_name,
                user_id=user.user_id,
                pin=user.pin,
                mac_address=user.mac_address,
                caller_id=user.caller_id,
                endpoint=user.endpoint,
                email=user.email,
                status=user.status,
                trunk_id=user.trunk_id,
                roles=user.roles,
                hashed_password=user.password  # In production, hash this password
            )
            
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            
            return schemas.CallCentreUserResponse.model_validate(db_user)
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create user: {str(e)}"
            )

    async def get_user(self, user_id: str) -> schemas.CallCentreUserResponse:
        """Get a call centre user by user_id"""
        try:
            user = self.db.query(models.CallCentreUser).filter(
                models.CallCentreUser.user_id == user_id
            ).first()
            
            if not user:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {user_id} not found"
                )
            
            return schemas.CallCentreUserResponse.model_validate(user)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get user: {str(e)}"
            )

    async def update_user(self, id: int, user: schemas.CallCentreUserUpdate) -> schemas.CallCentreUserResponse:
        """Update a call centre user"""
        try:
            logger.info(f"Attempting to update user with ID: {id}")
            
            # Log all available users for debugging
            all_users = self.db.query(models.CallCentreUser).all()
            logger.info(f"Available users in database: {[(u.id, u.user_id) for u in all_users]}")
            
            db_user = self.db.query(models.CallCentreUser).filter(
                models.CallCentreUser.id == id
            ).first()
            
            if not db_user:
                logger.error(f"User with ID {id} not found in database")
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {id} not found"
                )
            
            logger.info(f"Found user to update: {db_user.id} - {db_user.user_id}")
            
            # Update user fields
            update_data = user.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if key == 'password':
                    setattr(db_user, 'hashed_password', value)  # In production, hash this password
                else:
                    setattr(db_user, key, value)
            
            self.db.commit()
            self.db.refresh(db_user)
            
            logger.info(f"Successfully updated user: {db_user.id} - {db_user.user_id}")
            return schemas.CallCentreUserResponse.model_validate(db_user)
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating user: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update user: {str(e)}"
            )

    async def delete_user(self, id: int) -> None:
        """Delete a call centre user by ID"""
        try:
            db_user = self.db.query(models.CallCentreUser).filter(
                models.CallCentreUser.id == id
            ).first()
            
            if not db_user:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {id} not found"
                )
            
            self.db.delete(db_user)
            self.db.commit()
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete user: {str(e)}"
            )

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 10,
        status: Optional[int] = None,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        email: Optional[str] = None
    ) -> schemas.PaginatedUserResponse:
        """List all call centre users with pagination and optional filters"""
        try:
            # Build the base query
            query = self.db.query(models.CallCentreUser)
            
            # Apply filters if provided
            if status is not None:
                query = query.filter(models.CallCentreUser.status == status)
            if user_id:
                query = query.filter(models.CallCentreUser.user_id == user_id)
            if user_name:
                query = query.filter(models.CallCentreUser.user_name == user_name)
            if email:
                query = query.filter(models.CallCentreUser.email == email)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            users = query.offset(skip).limit(limit).all()
            
            # Calculate total pages
            pages = (total + limit - 1) // limit
            
            # Calculate current page
            current_page = (skip // limit) + 1
            
            return schemas.PaginatedUserResponse(
                items=[schemas.CallCentreUserResponse.model_validate(user) for user in users],
                total=total,
                page=current_page,
                size=limit,
                pages=pages
            )
            
        except Exception as e:
            logger.error(f"Error listing users: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list users: {str(e)}"
            )

    async def update_login_status(self, user_id: str, is_login: bool) -> schemas.CallCentreUserResponse:
        """Update user login/logout status"""
        try:
            db_user = self.db.query(models.CallCentreUser).filter(
                models.CallCentreUser.user_id == user_id
            ).first()
            
            if not db_user:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {user_id} not found"
                )
            
            if is_login:
                db_user.login_time = datetime.utcnow()
                db_user.status = "active"
            else:
                db_user.logout_time = datetime.utcnow()
                db_user.status = "inactive"
            
            self.db.commit()
            self.db.refresh(db_user)
            
            return schemas.CallCentreUserResponse.model_validate(db_user)
            
        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating login status: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update login status: {str(e)}"
            )

    async def get_user_by_id(self, id: int) -> schemas.CallCentreUserResponse:
        """Get a call centre user by ID"""
        try:
            user = self.db.query(models.CallCentreUser).filter(
                models.CallCentreUser.id == id
            ).first()
            
            if not user:
                raise HTTPException(
                    status_code=404,
                    detail=f"User with ID {id} not found"
                )
            
            return schemas.CallCentreUserResponse.model_validate(user)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get user: {str(e)}"
            )

    async def debug_database(self):
        """Debug database connection and table structure"""
        try:
            # Check if table exists
            result = self.db.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'call_centre_users')")
            table_exists = result.scalar()
            logger.info(f"Table 'call_centre_users' exists: {table_exists}")
            
            # Get table structure
            result = self.db.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'call_centre_users'
            """)
            columns = result.fetchall()
            logger.info(f"Table structure: {columns}")
            
            # Get all users
            users = self.db.query(models.CallCentreUser).all()
            logger.info(f"Total users in database: {len(users)}")
            for user in users:
                logger.info(f"User: ID={user.id}, user_id={user.user_id}")
            
        except Exception as e:
            logger.error(f"Database debug error: {str(e)}")
            raise

    async def debug_list_users(self) -> List[schemas.CallCentreUserResponse]:
        """Debug method to list all users with their IDs"""
        try:
            users = self.db.query(models.CallCentreUser).all()
            logger.info(f"Total users in database: {len(users)}")
            for user in users:
                logger.info(f"User: ID={user.id}, user_id={user.user_id}, user_name={user.user_name}")
            return [schemas.CallCentreUserResponse.model_validate(user) for user in users]
        except Exception as e:
            logger.error(f"Error in debug_list_users: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list users: {str(e)}"
            )
