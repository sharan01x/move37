#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Message models for the LifeScribe application.
"""

from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from enum import Enum

class MessageType(str, Enum):
    """Types of messages that can be sent between client and server."""
    STATUS_UPDATE = "status_update"
    AGENT_RESPONSE = "agent_response"
    QUALITY_UPDATE = "quality_update"
    RECALL_QUERY = "recall_query"
    RECORD_SUBMISSION = "record_submission"
    RECORD_RESPONSE = "record_response"
    
    # User Facts operations
    USER_FACTS_GET = "user_facts_get"
    USER_FACTS_GET_BY_ID = "user_facts_get_by_id"
    USER_FACTS_GET_BY_CATEGORY = "user_facts_get_by_category"
    USER_FACTS_SEARCH = "user_facts_search"
    USER_FACTS_ADD = "user_facts_add"
    USER_FACTS_UPDATE = "user_facts_update"
    USER_FACTS_DELETE = "user_facts_delete"
    USER_FACTS_RESPONSE = "user_facts_response"
    
    # File Management operations
    FILES_UPLOAD = "files_upload"
    FILES_LIST = "files_list"
    FILES_DELETE = "files_delete"
    FILES_TRANSCRIBE = "files_transcribe"
    FILES_RESPONSE = "files_response"
    FILES_SEMANTIC_SEARCH = "files_semantic_search"
    FILES_SEMANTIC_SEARCH_RESULTS = "files_semantic_search_results"
    
    # Record operations
    RECORD_UPDATE_TEXT = "record_update_text"

class BaseMessage(BaseModel):
    """Base message model with common fields."""
    type: MessageType
    data: Dict[str, Any]
    timestamp: float
    message_id: str

class StatusUpdateMessage(BaseMessage):
    """Message for status updates during processing."""
    type: MessageType = MessageType.STATUS_UPDATE
    data: Dict[str, Any]  # Contains message, operation_id, etc.

class AgentResponseMessage(BaseMessage):
    """Message containing agent responses."""
    type: MessageType = MessageType.AGENT_RESPONSE
    data: Dict[str, Any]  # Contains answer, agent_name, response_score, etc.

class QualityUpdateMessage(BaseMessage):
    """Message containing quality evaluation updates."""
    type: MessageType = MessageType.QUALITY_UPDATE
    data: Dict[str, Any]  # Contains updated scores and reasoning

class RecallQueryMessage(BaseMessage):
    """Message containing recall queries from the client."""
    type: MessageType = MessageType.RECALL_QUERY
    data: Dict[str, Any]  # Contains query, user_id, etc.

class RecordSubmissionMessage(BaseMessage):
    """Message containing record submissions from the client."""
    type: MessageType = MessageType.RECORD_SUBMISSION
    data: Dict[str, Any]  # Contains content, user_id, record_type, metadata

class RecordResponseMessage(BaseMessage):
    """Message containing record operation responses."""
    type: MessageType = MessageType.RECORD_RESPONSE
    data: Dict[str, Any]  # Contains success, message, record_id, etc.

# User Facts Message Models
class UserFactsGetMessage(BaseMessage):
    """Message for retrieving all user facts."""
    type: MessageType = MessageType.USER_FACTS_GET
    data: Dict[str, Any]  # Contains user_id

class UserFactsGetByIdMessage(BaseMessage):
    """Message for retrieving a specific user fact by ID."""
    type: MessageType = MessageType.USER_FACTS_GET_BY_ID
    data: Dict[str, Any]  # Contains user_id, fact_id

class UserFactsGetByCategoryMessage(BaseMessage):
    """Message for retrieving user facts by category."""
    type: MessageType = MessageType.USER_FACTS_GET_BY_CATEGORY
    data: Dict[str, Any]  # Contains user_id, category

class UserFactsSearchMessage(BaseMessage):
    """Message for searching user facts."""
    type: MessageType = MessageType.USER_FACTS_SEARCH
    data: Dict[str, Any]  # Contains user_id, query, top_k

class UserFactsAddMessage(BaseMessage):
    """Message for adding a new user fact."""
    type: MessageType = MessageType.USER_FACTS_ADD
    data: Dict[str, Any]  # Contains user_id, fact, category, source_text, confidence

class UserFactsUpdateMessage(BaseMessage):
    """Message for updating a user fact."""
    type: MessageType = MessageType.USER_FACTS_UPDATE
    data: Dict[str, Any]  # Contains user_id, fact_id, updates

class UserFactsDeleteMessage(BaseMessage):
    """Message for deleting a user fact."""
    type: MessageType = MessageType.USER_FACTS_DELETE
    data: Dict[str, Any]  # Contains user_id, fact_id

class UserFactsResponseMessage(BaseMessage):
    """Message containing user facts operation responses."""
    type: MessageType = MessageType.USER_FACTS_RESPONSE
    data: Dict[str, Any]  # Contains success, message, facts/fact

# File Management Message Models
class FilesUploadMessage(BaseMessage):
    """Message for uploading files."""
    type: MessageType = MessageType.FILES_UPLOAD
    data: Dict[str, Any]  # Contains user_id, files (base64 encoded)

class FilesListMessage(BaseMessage):
    """Message for listing files."""
    type: MessageType = MessageType.FILES_LIST
    data: Dict[str, Any]  # Contains user_id

class FilesDeleteMessage(BaseMessage):
    """Message for deleting a file."""
    type: MessageType = MessageType.FILES_DELETE
    data: Dict[str, Any]  # Contains user_id, file_id

class FilesResponseMessage(BaseMessage):
    """Message containing file operation responses."""
    type: MessageType = MessageType.FILES_RESPONSE
    data: Dict[str, Any]

class FilesTranscribeMessage(BaseMessage):
    """Message for transcribing file content."""
    type: MessageType = MessageType.FILES_TRANSCRIBE
    data: Dict[str, Any]  # Contains success, message, files/file_id