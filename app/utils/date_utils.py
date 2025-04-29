#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Date/time utilities for the Move 37 application.
"""

from datetime import datetime
from typing import Optional

# Constants for date/time formats
ISO_STORAGE_FORMAT = "%Y-%m-%d %H:%M:%S"  # For database storage
DISPLAY_DATE_FORMAT = "%d %b %Y"  # For date-only display
DISPLAY_DATETIME_FORMAT = "%d %b %Y %H:%M:%S"  # For date-time display

def format_for_storage(dt: Optional[datetime] = None) -> str:
    """Format datetime for storage in standard format."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime(ISO_STORAGE_FORMAT)

def format_date_for_display(dt: datetime) -> str:
    """Format date for display (e.g., '15 Mar 2025')."""
    return dt.strftime(DISPLAY_DATE_FORMAT)

def format_datetime_for_display(dt: datetime) -> str:
    """Format datetime for display (e.g., '15 Mar 2025 14:30:00')."""
    return dt.strftime(DISPLAY_DATETIME_FORMAT)

def parse_datetime(datetime_str: str) -> datetime:
    """Parse datetime from various formats to datetime object."""
    # Try different formats
    formats = [
        ISO_STORAGE_FORMAT,  # Standard storage format
        "%Y-%m-%dT%H:%M:%S",  # ISO format without microseconds
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
        "%Y-%m-%d %H:%M:%S.%f",  # Space-separated with microseconds
        DISPLAY_DATETIME_FORMAT,  # Display format (e.g., "19 Mar 2025 12:40:43")
    ]
    
    for fmt in formats:
        try:
            # For ISO format strings, remove timezone if present
            if 'T' in datetime_str:
                datetime_str = datetime_str.split('+')[0].split('Z')[0]
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Could not parse datetime string: {datetime_str}")

def standardize_timestamp(timestamp: str) -> str:
    """Convert any timestamp format to standard storage format."""
    try:
        dt = parse_datetime(timestamp)
        return format_for_storage(dt)
    except ValueError as e:
        return timestamp 