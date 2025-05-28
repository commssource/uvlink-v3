# ============================================================================
# shared/database.py - Fixed for sync operations
# ============================================================================

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi import Depends
import os
import logging

logger = logging.getLogger(__name__)

# Import from config
try:
    from config import DATABASE_URL, DATABASE_ECHO
except ImportError:
    # Fallback if config is not available
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./asterisk_manager.db")
    DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"

# Create engine based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        echo=DATABASE_ECHO,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
elif DATABASE_URL.startswith("mysql"):
    # MySQL configuration with sync driver
    engine = create_engine(
        DATABASE_URL,
        echo=DATABASE_ECHO,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=0
    )
else:
    # Default configuration
    engine = create_engine(DATABASE_URL, echo=DATABASE_ECHO)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class
Base = declarative_base()

# Dependency to get database session
def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize database
def init_database():
    """Initialize database tables"""
    try:
        # Test connection first
        with engine.connect() as connection:
            logger.info("✅ Database connection successful")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        print(f"❌ Database error: {e}")
        return False
