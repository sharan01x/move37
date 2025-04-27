#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Models for storing past conversations in the Move 37 application.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from app.utils.llm_utils import sanitize_non_ascii


class PastConversation(BaseModel):
    """Model for storing past conversations."""
    
    user_id: str = Field(..., description="User ID")
    query: str = Field(..., description="User's original query")
    answer: str = Field(..., description="System's answer to the query")
    agent_name: Optional[str] = Field(None, description="Name of the agent that provided the answer")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the conversation")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            # Add any custom JSON encoders here if needed
        }
    
    def model_dump(self, **kwargs):
        """Override to sanitize strings before serialization."""
        # Get the original model dump
        data = super().model_dump(**kwargs)
        
        # Sanitize string fields
        for field in ['query', 'answer', 'agent_name']:
            if data.get(field):
                data[field] = sanitize_non_ascii(data[field])
        
        # Process metadata if present
        if data.get('metadata'):
            for key, value in data['metadata'].items():
                if isinstance(value, str):
                    data['metadata'][key] = sanitize_non_ascii(value)
        
        return data
