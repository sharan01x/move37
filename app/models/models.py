#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Data models for the LifeScribe application.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from app.utils.llm_utils import sanitize_non_ascii
from app.utils.date_utils import format_for_storage, format_datetime_for_display


class MessageType(str, Enum):
    """Enum for message types."""
    INTERIM = "interim"
    FINAL = "final"


class OperationType(str, Enum):
    """Enum for operation types."""
    RECORD = "Record"
    RECALL = "Recall"


class DataType(str, Enum):
    """Enum for data types."""
    TEXT = "text"
    VOICE = "voice"
    FILE = "file"
    COMBINED = "combined"


class DataPackage(BaseModel):
    """Data package for processing operations."""
    user_id: str
    operation_type: OperationType
    data_type: DataType
    text_content: Optional[str] = None
    voice_content: Optional[bytes] = None
    file_content: Optional[bytes] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # New field for additional metadata
    target_agent: Optional[str] = None  # For recall operations
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the data package")
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: format_for_storage
        }


class NamedEntity(BaseModel):
    """Named entity model."""
    entity: str = Field(..., description="Named entity")
    entity_type: str = Field(..., description="Entity type")
    context: str = Field(..., description="Context in which the entity appears")
    source_id: str = Field(..., description="ID of the source transcription")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the named entity recognition")
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: format_for_storage
        }


class TranscriptionResult(BaseModel):
    """Transcription result model."""
    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(..., description="Confidence score of the transcription")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class RecordResponse(BaseModel):
    """Response model for record operation."""
    success: bool = Field(..., description="Success status")
    message: str = Field(..., description="Response message")
    transcription: Optional[str] = Field(None, description="Transcription if voice data was provided")
    record_id: Optional[str] = Field(None, description="ID of the recorded data")
    file_path: Optional[str] = Field(None, description="Path to the saved file if file data was provided")


class RecallResponse(BaseModel):
    """Response model for recall operation."""
    message: str = Field(..., description="Response message")
    answer: Optional[str] = Field(None, description="Answer to the query")
    agent_name: Optional[str] = Field(None, description="Name of the agent that provided the answer")
    relevant_sources: Optional[List[Dict[str, Any]]] = Field(None, description="Relevant sources used to answer the query")
    response_score: Optional[int] = Field(None, description="Quality score for the response")
    is_math_tool_query: Optional[bool] = Field(None, description="Indicates if the query is a math tool query")
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            # Add any custom JSON encoders here if needed
        }
    
    def model_dump(self, **kwargs):
        """Override to sanitize strings before serialization."""
        # Get the original model dump
        data = super().model_dump(**kwargs)
        
        # Sanitize the message and answer fields
        if data.get('message'):
            data['message'] = sanitize_non_ascii(data['message'])
        
        if data.get('answer'):
            data['answer'] = sanitize_non_ascii(data['answer'])
            
        if data.get('agent_name'):
            data['agent_name'] = sanitize_non_ascii(data['agent_name'])
        
        # Process relevant_sources if present
        if data.get('relevant_sources'):
            for source in data['relevant_sources']:
                for key, value in source.items():
                    if isinstance(value, str):
                        source[key] = sanitize_non_ascii(value)
        
        return data


class InterimMessageResponse(BaseModel):
    """Model for interim messages during processing."""
    message_type: MessageType = Field(MessageType.INTERIM, description="Type of message (interim or final)")
    message: str = Field(..., description="The interim message content")
    operation_id: str = Field(..., description="Unique ID for the operation being processed")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp of the interim message")
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: format_for_storage
        }
    
    def model_dump(self, **kwargs):
        """Override to sanitize strings before serialization."""
        # Get the original model dump
        data = super().model_dump(**kwargs)
        
        # Sanitize the message field
        if data.get('message'):
            data['message'] = sanitize_non_ascii(data['message'])
        
        return data
