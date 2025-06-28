"""
Database management module for FastAPI application
Handles database connections, sessions, and health checks
"""

import logging
from typing import AsyncGenerator, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text, pool
from sqlalchemy.exc import SQLAlchemyError
import asyncio
from contextlib import asynccontextmanager

from config import get_settings

# Get settings
settings = get_settings()

# Initialize logger
logger = logging.getLogger(__name__)

# Create declarative base for models
Base = declarative_base()

# Global database engine and session maker
engine = None
async_session_maker = None

# ============================================================================
# DATABASE ENGINE SETUP
# ============================================================================

def create_database_engine():
    """Create async database engine with proper configuration"""
    global engine
    
    if engine is not None:
        return engine
    
    # Database configuration
    database_url = getattr(settings, 'database_url', 'sqlite+aiosqlite:///./app.db')
    
    # Engine configuration based on database type
    engine_kwargs = {
        "echo": settings.debug,  # Log SQL queries in debug mode
        "future": True,
    }
    
    # SQLite specific configuration
    if 'sqlite' in database_url:
        engine_kwargs.update({
            "poolclass": pool.StaticPool,
            "connect_args": {
                "check_same_thread": False,
                "timeout": 20
            },
        })
    
    # PostgreSQL specific configuration
    elif 'postgresql' in database_url:
        engine_kwargs.update({
            "pool_size": getattr(settings, 'db_pool_size', 10),
            "max_overflow": getattr(settings, 'db_max_overflow', 20),
            "pool_timeout": getattr(settings, 'db_pool_timeout', 30),
            "pool_recycle": getattr(settings, 'db_pool_recycle', 3600),
            "pool_pre_ping": True,
        })
    
    # MySQL specific configuration
    elif 'mysql' in database_url:
        engine_kwargs.update({
            "pool_size": getattr(settings, 'db_pool_size', 10),
            "max_overflow": getattr(settings, 'db_max_overflow', 20),
            "pool_timeout": getattr(settings, 'db_pool_timeout', 30),
            "pool_recycle": getattr(settings, 'db_pool_recycle', 3600),
            "pool_pre_ping": True,
        })
    
    try:
        engine = create_async_engine(database_url, **engine_kwargs)
        logger.info(f"Database engine created successfully for: {database_url.split('@')[-1] if '@' in database_url else database_url}")
        return engine
        
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        raise

def create_session_maker():
    """Create async session maker"""
    global async_session_maker
    
    if async_session_maker is not None:
        return async_session_maker
    
    if engine is None:
        create_database_engine()
    
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False,
    )
    
    logger.info("Database session maker created successfully")
    return async_session_maker

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

async def init_database():
    """Initialize database connection and create tables if needed"""
    try:
        # Create engine and session maker
        create_database_engine()
        create_session_maker()
        
        # Test connection
        async with engine.begin() as conn:
            # Simple connection test
            await conn.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
        
        # Create tables if they don't exist
        await create_tables()
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def create_tables():
    """Create database tables if they don't exist"""
    try:
        # Import all your models here to ensure they're registered with Base
        # from apps.endpoints.models import EndpointModel
        # from apps.provisioning.models import ProvisioningModel
        # ... import other models ...
        
        async with engine.begin() as conn:
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created/verified successfully")
            
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

# ============================================================================
# DATABASE SESSION MANAGEMENT
# ============================================================================

async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session
    Use this in your FastAPI route dependencies
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

@asynccontextmanager
async def get_db_session():
    """
    Context manager for database sessions
    Use this for manual database operations
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

# ============================================================================
# DATABASE HEALTH CHECK
# ============================================================================

async def get_database_status() -> Dict[str, Any]:
    """
    Get database health status
    Returns connection status, basic stats, etc.
    """
    status = {
        "status": "unknown",
        "engine_status": "not_initialized",
        "connection_test": False,
        "error": None
    }
    
    try:
        if engine is None:
            status["error"] = "Database engine not initialized"
            return status
        
        status["engine_status"] = "initialized"
        
        # Test connection with timeout
        async with asyncio.timeout(5.0):  # 5 second timeout
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                
                if test_value == 1:
                    status["connection_test"] = True
                    status["status"] = "healthy"
                else:
                    status["error"] = "Unexpected test query result"
                    status["status"] = "unhealthy"
        
        # Get additional database info if connection is healthy
        if status["status"] == "healthy":
            try:
                async with engine.begin() as conn:
                    # Database-specific queries
                    if 'sqlite' in str(engine.url):
                        result = await conn.execute(text("PRAGMA database_list"))
                        status["database_type"] = "sqlite"
                    elif 'postgresql' in str(engine.url):
                        result = await conn.execute(text("SELECT version()"))
                        version = result.scalar()
                        status["database_type"] = "postgresql"
                        status["version"] = version
                    elif 'mysql' in str(engine.url):
                        result = await conn.execute(text("SELECT VERSION()"))
                        version = result.scalar()
                        status["database_type"] = "mysql"
                        status["version"] = version
                    
                    # Get pool status if available
                    if hasattr(engine.pool, 'size'):
                        status["pool_info"] = {
                            "size": engine.pool.size(),
                            "checked_in": engine.pool.checkedin(),
                            "checked_out": engine.pool.checkedout(),
                        }
                        
            except Exception as e:
                logger.warning(f"Could not get extended database info: {e}")
                # Don't fail health check for extended info
    
    except asyncio.TimeoutError:
        status["error"] = "Database connection timeout"
        status["status"] = "timeout"
    except SQLAlchemyError as e:
        status["error"] = f"Database error: {str(e)}"
        status["status"] = "error"
    except Exception as e:
        status["error"] = f"Unexpected error: {str(e)}"
        status["status"] = "error"
    
    return status

async def check_database_health() -> bool:
    """Simple boolean database health check"""
    try:
        status = await get_database_status()
        return status["status"] == "healthy"
    except Exception:
        return False

# ============================================================================
# DATABASE CLEANUP
# ============================================================================

async def close_database():
    """Close database connections and cleanup"""
    global engine, async_session_maker
    
    try:
        if engine is not None:
            await engine.dispose()
            logger.info("Database engine disposed successfully")
        
        engine = None
        async_session_maker = None
        
        logger.info("Database cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")

# ============================================================================
# DATABASE UTILITIES
# ============================================================================

async def execute_raw_query(query: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Execute a raw SQL query
    Use with caution - prefer ORM operations when possible
    """
    async with get_db_session() as session:
        try:
            if params:
                result = await session.execute(text(query), params)
            else:
                result = await session.execute(text(query))
            
            return result.fetchall()
            
        except Exception as e:
            logger.error(f"Raw query execution failed: {e}")
            raise

async def get_table_count(table_name: str) -> int:
    """Get row count for a specific table"""
    try:
        async with get_db_session() as session:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            return result.scalar() or 0
    except Exception as e:
        logger.error(f"Failed to get count for table {table_name}: {e}")
        return -1

async def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database"""
    try:
        async with get_db_session() as session:
            # Database-specific table existence check
            if 'sqlite' in str(engine.url):
                result = await session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"),
                    {"table_name": table_name}
                )
            elif 'postgresql' in str(engine.url):
                result = await session.execute(
                    text("SELECT tablename FROM pg_tables WHERE tablename=:table_name"),
                    {"table_name": table_name}
                )
            elif 'mysql' in str(engine.url):
                result = await session.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_name=:table_name"),
                    {"table_name": table_name}
                )
            else:
                # Generic approach
                result = await session.execute(text(f"SELECT 1 FROM {table_name} LIMIT 1"))
            
            return result.fetchone() is not None
            
    except Exception:
        return False

# ============================================================================
# MIGRATION UTILITIES
# ============================================================================

async def run_migration_script(script_path: str):
    """Run a SQL migration script"""
    try:
        with open(script_path, 'r') as f:
            sql_content = f.read()
        
        # Split by semicolon and execute each statement
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        async with get_db_session() as session:
            for statement in statements:
                await session.execute(text(statement))
        
        logger.info(f"Migration script {script_path} executed successfully")
        
    except Exception as e:
        logger.error(f"Failed to run migration script {script_path}: {e}")
        raise

# ============================================================================
# DATABASE BACKUP/RESTORE (SQLite specific)
# ============================================================================

async def backup_sqlite_database(backup_path: str) -> bool:
    """Backup SQLite database (only works for SQLite)"""
    if 'sqlite' not in str(engine.url):
        logger.warning("Database backup only supported for SQLite")
        return False
    
    try:
        import shutil
        from urllib.parse import urlparse
        
        # Extract database file path from URL
        db_url = str(engine.url)
        if '///' in db_url:
            db_path = db_url.split('///')[-1]
        else:
            db_path = db_url.split('//')[-1]
        
        # Create backup
        shutil.copy2(db_path, backup_path)
        logger.info(f"Database backed up to {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return False

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

"""
Example usage in your FastAPI routes:

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database import get_database_session

@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_database_session)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users

# Or using context manager:
async def some_function():
    async with get_db_session() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        return users
"""

# ============================================================================
# TESTING UTILITIES
# ============================================================================

async def create_test_database():
    """Create a test database (useful for testing)"""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    return test_engine

# ============================================================================
# DEPENDENCY FUNCTIONS FOR FASTAPI
# ============================================================================

# Main dependency function that you'll use in your FastAPI routes
def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions"""
    return get_database_session()

# Alternative dependency if you need different session config
async def get_db_read_only() -> AsyncGenerator[AsyncSession, None]:
    """Read-only database session dependency"""
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_maker() as session:
        try:
            # Configure session for read-only operations
            await session.execute(text("SET TRANSACTION READ ONLY"))
            yield session
        except Exception as e:
            logger.error(f"Read-only database session error: {e}")
            raise
        finally:
            await session.close()