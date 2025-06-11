"""
Custom Pydantic fields for UK date/time formatting with timezone support
File: app/utils/custom_fields.py
"""

from typing import Any, Optional
from datetime import datetime
import pytz
from pydantic import Field
from typing_extensions import Annotated

# UK timezone with automatic DST handling
UK_TIMEZONE = pytz.timezone('Europe/London')

def uk_datetime_validator(v: Any) -> Optional[str]:
    """
    Validator to convert any datetime input to UK format: DD/MM/YYYY HH:MM:SS (24-hour)
    Automatically handles UK daylight saving time (BST/GMT)
    
    Args:
        v: Input value (can be datetime, string, or None)
        
    Returns:
        Formatted UK datetime string with DST applied or None
    """
    if v is None:
        return None
    
    if isinstance(v, datetime):
        # If datetime is naive (no timezone), assume it's UTC
        if v.tzinfo is None:
            v = pytz.UTC.localize(v)
        
        # Convert to UK timezone (automatically handles BST/GMT)
        uk_time = v.astimezone(UK_TIMEZONE)
        
        # Format as 24-hour DD/MM/YYYY HH:MM:SS
        return uk_time.strftime("%d/%m/%Y %H:%M:%S")
        
    elif isinstance(v, str):
        try:
            # Parse ISO format datetime string
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            
            # If no timezone info, assume UTC
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            
            # Convert to UK timezone
            uk_time = dt.astimezone(UK_TIMEZONE)
            
            # Format as 24-hour DD/MM/YYYY HH:MM:SS
            return uk_time.strftime("%d/%m/%Y %H:%M:%S")
            
        except (ValueError, TypeError):
            # If parsing fails, return the original string
            return v
    
    # For any other type, convert to string
    return str(v)

def uk_date_validator(v: Any) -> Optional[str]:
    """
    Validator to convert any datetime input to UK date format: DD/MM/YYYY
    
    Args:
        v: Input value (can be datetime, string, or None)
        
    Returns:
        Formatted UK date string or None
    """
    if v is None:
        return None
    
    if isinstance(v, datetime):
        # Handle timezone conversion for date as well
        if v.tzinfo is None:
            v = pytz.UTC.localize(v)
        uk_time = v.astimezone(UK_TIMEZONE)
        return uk_time.strftime("%d/%m/%Y")
        
    elif isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            uk_time = dt.astimezone(UK_TIMEZONE)
            return uk_time.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return v
    
    return str(v)

def uk_time_validator(v: Any) -> Optional[str]:
    """
    Validator to convert any datetime input to UK time format: HH:MM:SS (24-hour)
    
    Args:
        v: Input value (can be datetime, string, or None)
        
    Returns:
        Formatted UK time string (24-hour) or None
    """
    if v is None:
        return None
    
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = pytz.UTC.localize(v)
        uk_time = v.astimezone(UK_TIMEZONE)
        return uk_time.strftime("%H:%M:%S")  # 24-hour format
        
    elif isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            uk_time = dt.astimezone(UK_TIMEZONE)
            return uk_time.strftime("%H:%M:%S")  # 24-hour format
        except (ValueError, TypeError):
            return v
    
    return str(v)

def uk_datetime_12h_validator(v: Any) -> Optional[str]:
    """
    Validator to convert any datetime input to UK 12-hour format: DD/MM/YYYY HH:MM:SS AM/PM
    
    Args:
        v: Input value (can be datetime, string, or None)
        
    Returns:
        Formatted UK 12-hour datetime string or None
    """
    if v is None:
        return None
    
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = pytz.UTC.localize(v)
        uk_time = v.astimezone(UK_TIMEZONE)
        return uk_time.strftime("%d/%m/%Y %I:%M:%S %p")
        
    elif isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            uk_time = dt.astimezone(UK_TIMEZONE)
            return uk_time.strftime("%d/%m/%Y %I:%M:%S %p")
        except (ValueError, TypeError):
            return v
    
    return str(v)

def uk_datetime_long_validator(v: Any) -> Optional[str]:
    """
    Validator for long UK format: DD Month YYYY HH:MM:SS (24-hour)
    Example: 11 June 2025 18:17:07
    """
    if v is None:
        return None
    
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = pytz.UTC.localize(v)
        uk_time = v.astimezone(UK_TIMEZONE)
        return uk_time.strftime("%d %B %Y %H:%M:%S")  # 24-hour format
        
    elif isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)
            uk_time = dt.astimezone(UK_TIMEZONE)
            return uk_time.strftime("%d %B %Y %H:%M:%S")  # 24-hour format
        except (ValueError, TypeError):
            return v
    
    return str(v)

# Annotated types for different UK date/time formats
UKDateTime = Annotated[
    Optional[str], 
    Field(description="Date and time in UK format with DST (DD/MM/YYYY HH:MM:SS)")
]

UKDate = Annotated[
    Optional[str], 
    Field(description="Date in UK format (DD/MM/YYYY)")
]

UKTime = Annotated[
    Optional[str], 
    Field(description="Time in UK format 24-hour (HH:MM:SS)")
]

UKDateTime12H = Annotated[
    Optional[str], 
    Field(description="Date and time in UK 12-hour format (DD/MM/YYYY HH:MM:SS AM/PM)")
]

UKDateTimeLong = Annotated[
    Optional[str], 
    Field(description="Date and time in UK long format (DD Month YYYY HH:MM:SS)")
]

# Export all validators for easy importing
__all__ = [
    'uk_datetime_validator',
    'uk_date_validator', 
    'uk_time_validator',
    'uk_datetime_12h_validator',
    'uk_datetime_long_validator',
    'UKDateTime',
    'UKDate',
    'UKTime', 
    'UKDateTime12H',
    'UKDateTimeLong'
]