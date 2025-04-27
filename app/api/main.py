#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API endpoints for the Move 37 application.
"""

import os
import base64
import asyncio
from typing import Dict, Any, Optional, List, Callable
from fastapi import FastAPI, UploadFile, File, Form, Depends, Body, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import uuid
from fastapi import WebSocket, WebSocketDisconnect
import time

# Set up logger
logger = logging.getLogger(__name__)

from app.models.models import DataPackage, RecordResponse, RecallResponse, OperationType, DataType
from app.agents.conductor_agent import ConductorAgent
from app.core.config import API_HOST, API_PORT, FILE_DB_PATH, SOCIAL_MEDIA_TEMP_PATH, MAX_FILE_SIZE, ALLOWED_FILE_TYPES
from app.database.user_facts_db import UserFactsDBInterface
from app.database.file_db import FileDBInterface
from app.messaging.websocket import WebSocketConnectionHandler
from app.models.messages import (MessageType, RecallQueryMessage, StatusUpdateMessage, AgentResponseMessage, 
    QualityUpdateMessage, RecordSubmissionMessage, RecordResponseMessage, UserFactsGetMessage, 
    UserFactsGetByIdMessage, UserFactsGetByCategoryMessage, UserFactsSearchMessage, UserFactsAddMessage, 
    UserFactsUpdateMessage, UserFactsDeleteMessage, UserFactsResponseMessage, FilesUploadMessage, 
    FilesListMessage, FilesDeleteMessage, FilesResponseMessage, FilesTranscribeMessage)
from app.utils.file_processor import FileProcessor


# Create the FastAPI app
app = FastAPI(
    title="Move 37 API",
    description="API for the Move 37 application with support for streaming and interim messages",
    version="1.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Initialize the conductor agent
# Using a default user ID for the global instance
# This aligns with the application's transition to a user-ID-based architecture
DEFAULT_USER_ID = "default"
user_facts_db = UserFactsDBInterface(user_id=DEFAULT_USER_ID)
conductor_agent = ConductorAgent()

# Initialize file database
# Using the same default user ID for consistency
file_db = FileDBInterface(user_id=DEFAULT_USER_ID)

# Initialize file processor
file_processor = FileProcessor(file_db)

# Initialize WebSocket handler
websocket_handler = WebSocketConnectionHandler()


@app.get("/")
async def root():
    """
    Root endpoint.
    
    Returns:
        Welcome message.
    """
    return {"message": "Welcome to the Move 37 API"}


@app.post("/record", response_model=RecordResponse)
async def record(
    user_id: str = Form(...),
    text_content: Optional[str] = Form(None),
    voice_file: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Record endpoint.
    
    Args:
        user_id: User ID.
        text_content: Text content.
        voice_file: Voice file.
        file: Additional file.
        
    Returns:
        Record response.
    """
    # Determine the data type
    data_type = DataType.TEXT
    if voice_file and text_content:
        data_type = DataType.COMBINED
    elif voice_file:
        data_type = DataType.VOICE
    elif file:
        data_type = DataType.FILE
    
    # Read the voice file if present
    voice_content = None
    if voice_file:
        voice_content = await voice_file.read()
    
    # Read the file if present
    file_content = None
    file_name = None
    file_type = None
    if file:
        file_content = await file.read()
        file_name = file.filename
        file_type = file.content_type
    
    # Create the data package
    data_package = DataPackage(
        user_id=user_id,
        operation_type=OperationType.RECORD,
        data_type=data_type,
        text_content=text_content,
        voice_content=voice_content,
        file_content=file_content,
        file_name=file_name,
        file_type=file_type
    )
    
    # Process the data package
    response = conductor_agent.process_data_package(data_package)
    
    return response


class RecallRequest(BaseModel):
    user_id: str
    query: str
    target_agent: Optional[str] = None


@app.post("/recall", response_model=None)
async def recall(
    request: RecallRequest
):
    """
    Recall endpoint for JSON requests.
    
    Args:
        request: RecallRequest object with user_id and query fields.
        
    Returns:
        Recall response.
    """
    # Create the data package
    data_package = DataPackage(
        user_id=request.user_id,
        operation_type=OperationType.RECALL,
        data_type=DataType.TEXT,
        text_content=request.query,
        target_agent=request.target_agent
    )
    
    # Process the recall operation through the conductor agent
    return await conductor_agent.process_recall_operation(data_package)


@app.post("/recall-form", response_model=None)
async def recall_form(
    user_id: str = Form(...),
    query: str = Form(...),
    target_agent: Optional[str] = Form(None)
):
    """
    Recall endpoint for form data requests.
    
    Args:
        user_id: User ID.
        query: Query to search for.
        target_agent: Optional target agent to handle the query.
        
    Returns:
        Recall response.
    """
    # Create a RecallRequest and forward to the main recall endpoint
    request = RecallRequest(
        user_id=user_id, 
        query=query,
        target_agent=target_agent
    )
    return await recall(request)


@app.websocket("/ws/recall")
async def websocket_recall(websocket: WebSocket):
    """
    WebSocket endpoint for READ operations (recall queries, user facts retrieval, file listing).
    This endpoint handles all data retrieval operations regardless of data type.
    
    Args:
        websocket: WebSocket connection.
    """
    client_id = str(uuid.uuid4())
    
    # Register message handlers
    async def handle_recall_query(client_id: str, message: dict):
        """Handle recall query messages."""
        try:
            # Extract query data
            data = message.get("data", {})
            query = data.get("query")
            user_id = data.get("user_id")
            target_agent = data.get("target_agent", "all")  # Default to 'all' if not specified
            query_id = data.get("query_id")
            
            # Extract attachment file path for Butterfly agent if available
            attachment_file_path = data.get("attachment_file_path") if target_agent == "butterfly" else None
            
            if not all([query, user_id]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: query and user_id"}
                )
                return
            
            # Create the data package
            data_package = DataPackage(
                user_id=user_id,
                operation_type=OperationType.RECALL,
                data_type=DataType.TEXT,
                text_content=query,
                metadata={
                    "target_agent": target_agent,
                    "query_id": query_id
                }
            )
            
            # Define message callback
            async def message_callback(message: dict):
                """Callback to send messages to the client."""
                await websocket_handler.message_service.send_message(
                    client_id,
                    message["type"],
                    message["data"]
                )
            
            # Process the recall operation with the message callback
            try:
                # For Butterfly agent with attachment, pass the attachment file path
                if target_agent == "butterfly" and attachment_file_path:
                    print(f"Passing attachment file path to Butterfly agent: {attachment_file_path}")
                    response = await conductor_agent.process_recall_operation(
                        data_package, 
                        message_callback,
                        attachment_file_path=attachment_file_path
                    )
                else:
                    response = await conductor_agent.process_recall_operation(data_package, message_callback)
                
                if not isinstance(response, RecallResponse):
                    response = RecallResponse(
                        success=True,
                        message="Successfully executed recall operation"
                    )
            except Exception as e:
                print(f"Error in process_recall_operation: {e}")
                response = RecallResponse(
                    success=False,
                    message=f"Error executing recall operation: {str(e)}"
                )
            
            # Send the final response back to the client
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.RECORD_RESPONSE,
                response.dict()
            )
            
        except Exception as e:
            print(f"Error in handle_recall_query: {e}")
            # Send error message to client
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error processing query: {str(e)}"}
            )
    
    # User Facts Handlers (Migrated from /ws/user-facts endpoint)
    async def handle_user_facts_get(client_id: str, message: dict):
        """Handle get all user facts messages."""
        try:
            user_id = message.get("data", {}).get("user_id")
            
            if not user_id:
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required field: user_id"}
                )
                return
            
            # Get user facts
            facts = user_facts_db.get_all_facts(user_id=user_id)
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": True,
                    "message": "Successfully retrieved user facts",
                    "facts": facts
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_get: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error retrieving user facts: {str(e)}"}
            )
    
    async def handle_user_facts_get_by_id(client_id: str, message: dict):
        """Handle get user fact by ID messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            fact_id = data.get("fact_id")
            
            if not all([user_id, fact_id]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and fact_id"}
                )
                return
            
            # Get user fact
            fact = user_facts_db.get_fact_by_id(fact_id=fact_id, user_id=user_id)
            
            if not fact:
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.USER_FACTS_RESPONSE,
                    {
                        "success": False,
                        "message": f"Fact with ID {fact_id} not found"
                    }
                )
                return
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": True,
                    "message": "Successfully retrieved user fact",
                    "fact": fact
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_get_by_id: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error retrieving user fact: {str(e)}"}
            )
    
    async def handle_user_facts_get_by_category(client_id: str, message: dict):
        """Handle get user facts by category messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            category = data.get("category")
            
            if not all([user_id, category]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and category"}
                )
                return
            
            # Get user facts by category
            facts = user_facts_db.get_facts_by_category(category=category, user_id=user_id)
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": True,
                    "message": f"Successfully retrieved user facts in category {category}",
                    "facts": facts
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_get_by_category: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error retrieving user facts by category: {str(e)}"}
            )
    
    async def handle_user_facts_search(client_id: str, message: dict):
        """Handle search user facts messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            query = data.get("query")
            top_k = data.get("top_k", 5)
            
            if not all([user_id, query]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and query"}
                )
                return
            
            # Search user facts
            facts = user_facts_db.search_facts(query=query, user_id=user_id, top_k=top_k)
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": True,
                    "message": f"Successfully searched user facts for '{query}'",
                    "facts": facts
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_search: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error searching user facts: {str(e)}"}
            )
    
    async def handle_user_facts_add(client_id: str, message: dict):
        """Handle add user fact messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            fact = data.get("fact")
            category = data.get("category")
            source_text = data.get("source_text")
            confidence = data.get("confidence")
            
            if not all([user_id, fact]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and fact"}
                )
                return
            
            # Add user fact
            new_fact = user_facts_db.add_fact(
                fact=fact,
                category=category,
                source_text=source_text,
                confidence=confidence,
                user_id=user_id
            )
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": True,
                    "message": "Successfully added user fact",
                    "fact": new_fact
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_add: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error adding user fact: {str(e)}"}
            )
    
    async def handle_user_facts_update(client_id: str, message: dict):
        """Handle update user fact messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            fact_id = data.get("fact_id")
            updates = data.get("updates", {})
            
            if not all([user_id, fact_id, updates]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id, fact_id, and updates"}
                )
                return
            
            # Update user fact
            updated_fact = user_facts_db.update_fact(fact_id=fact_id, updates=updates, user_id=user_id)
            
            if not updated_fact:
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.USER_FACTS_RESPONSE,
                    {
                        "success": False,
                        "message": f"Fact with ID {fact_id} not found"
                    }
                )
                return
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": True,
                    "message": "Successfully updated user fact",
                    "fact": updated_fact
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_update: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error updating user fact: {str(e)}"}
            )
    
    async def handle_user_facts_delete(client_id: str, message: dict):
        """Handle delete user fact messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            fact_id = data.get("fact_id")
            
            if not all([user_id, fact_id]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and fact_id"}
                )
                return
            
            # Delete user fact
            success = user_facts_db.delete_fact(fact_id=fact_id, user_id=user_id)
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": success,
                    "message": "Successfully deleted user fact" if success else f"Fact with ID {fact_id} not found"
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_delete: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error deleting user fact: {str(e)}"}
            )
    
    # File Operations READ Handlers
    async def handle_files_list(client_id: str, message: dict):
        """Handle list files messages."""
        try:
            user_id = message.get("data", {}).get("user_id")
            
            if not user_id:
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required field: user_id"}
                )
                return
            
            # List files
            files = file_db.list_files(user_id=user_id)
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.FILES_RESPONSE,
                {
                    "success": True,
                    "message": "Successfully retrieved files",
                    "files": files
                }
            )
            
        except Exception as e:
            print(f"Error in handle_files_list: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error listing files: {str(e)}"}
            )
    
    # Register the recall (READ) operations
    websocket_handler.message_service.register_handler(MessageType.RECALL_QUERY, handle_recall_query)
    
    # Register user facts READ handlers
    websocket_handler.message_service.register_handler(MessageType.USER_FACTS_GET, handle_user_facts_get)
    websocket_handler.message_service.register_handler(MessageType.USER_FACTS_GET_BY_ID, handle_user_facts_get_by_id)
    websocket_handler.message_service.register_handler(MessageType.USER_FACTS_GET_BY_CATEGORY, handle_user_facts_get_by_category)
    websocket_handler.message_service.register_handler(MessageType.USER_FACTS_SEARCH, handle_user_facts_search)
    
    # Register file READ operations
    websocket_handler.message_service.register_handler(MessageType.FILES_LIST, handle_files_list)
    
    # Handle the connection
    await websocket_handler.handle_connection(websocket, client_id)


# User Facts model class definition (kept for WebSocket handlers)

class UserFactRequest(BaseModel):
    """Request model for user facts operations."""
    fact: Optional[str] = None
    category: Optional[str] = None
    source_text: Optional[str] = None
    confidence: Optional[float] = None
    fact_id: Optional[str] = None
    updates: Optional[Dict[str, Any]] = None
    query: Optional[str] = None
    top_k: Optional[int] = 5

# NOTE: User Facts REST API endpoints have been removed.
# All user facts operations are now handled via WebSocket connections:
# - READ operations (get, search) via /ws/recall
# - WRITE operations (add, update, delete) via /ws/record


# File Management API Endpoints

class FileUploadResponse(BaseModel):
    """Response model for file upload."""
    success: bool
    message: str
    file_ids: List[str]

class FileTextContentUpdateRequest(BaseModel):
    """Request model for updating file text content."""
    file_id: str
    user_id: str
    text_content: str

class FileTextContentUpdateResponse(BaseModel):
    """Response model for file text content update."""
    success: bool
    message: str
    file_id: str

class FileListResponse(BaseModel):
    """Response model for file list."""
    success: bool
    message: str
    files: List[Dict[str, Any]]

@app.post("/files/upload", response_model=FileUploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    user_id: str = Form(...)
):
    """Upload files endpoint.
    
    Args:
        files: List of files to upload.
        user_id: ID of the user uploading the files.
        
    Returns:
        FileUploadResponse with upload status.
    """
    try:
        # Create user-specific directory
        user_dir = os.path.join(FILE_DB_PATH, user_id)
        os.makedirs(user_dir, exist_ok=True)
        
        file_ids = []
        for file in files:
            # Debug logging for file MIME types
            logger.debug(f"File upload: {file.filename}, MIME type: {file.content_type}")
            print(f"File upload: {file.filename}, MIME type: {file.content_type}")
            
            # Check if it's a markdown file by extension (regardless of reported MIME type)
            file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
            is_markdown = file_extension == 'md'
            
            # Override content_type for markdown files
            content_type = file.content_type
            if is_markdown:
                content_type = 'text/markdown'
                logger.debug(f"Detected Markdown file by extension: {file.filename}")
                print(f"Detected Markdown file by extension: {file.filename}")
            
            # Validate file type
            if content_type not in ALLOWED_FILE_TYPES:
                logger.warning(f"File type not allowed: {content_type} for file {file.filename}")
                print(f"File type not allowed: {content_type} for file {file.filename}")
                continue
            
            # Validate file size
            file_size = 0
            file_content = await file.read()
            file_size = len(file_content)
            
            if file_size > MAX_FILE_SIZE:
                continue
            
            # Use original filename
            file_path = os.path.join(user_dir, file.filename)
            
            # Check if file exists
            if os.path.exists(file_path):
                # Let the frontend handle the conflict
                continue
            
            # Save file
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Add to database
            file_id = file_db.add_file(
                file_name=file.filename,
                file_path=file_path,
                file_type=content_type,  # Use the corrected content type
                file_size=file_size,
                user_id=user_id
            )
            # Set initial status to processing for transcription
            file_db.update_file_status(file_id, "processing")
            
            # Trigger transcription in the background
            print(f"REST endpoint: Triggering transcription for file ID: {file_id}")
            try:
                # Create a background task for transcription
                asyncio.create_task(file_processor.process_file(file_id, user_id))
                print(f"REST endpoint: Transcription task created for file ID: {file_id}")
            except Exception as e:
                print(f"REST endpoint: Error creating transcription task: {str(e)}")
                # If transcription fails, mark as complete anyway
                file_db.update_file_status(file_id, "complete")
            
            file_ids.append(file_id)
        
        if not file_ids:
            return FileUploadResponse(
                success=False,
                message="No valid files were uploaded.",
                file_ids=[]
            )
        
        return FileUploadResponse(
            success=True,
            message=f"Successfully uploaded {len(file_ids)} files.",
            file_ids=file_ids
        )
        
    except Exception as e:
        logger.error(f"Error uploading files: {e}")
        return FileUploadResponse(
            success=False,
            message=f"Error uploading files: {str(e)}",
            file_ids=[]
        )

@app.post("/social_media/upload", response_model=FileUploadResponse)
async def upload_social_media_image(
    file: UploadFile = File(...),
    user_id: str = Form(...)
):
    """Upload a single image for social media posting.
    
    Args:
        file: Image file to upload
        user_id: ID of the user uploading the file
        
    Returns:
        FileUploadResponse with upload status and file path in file_ids
    """
    try:
        # Create user-specific directory
        user_dir = os.path.join(SOCIAL_MEDIA_TEMP_PATH, user_id)
        os.makedirs(user_dir, exist_ok=True)
        
        print(f"Social media upload - User directory: {user_dir}")
        
        # Validate file is an image by extension
        file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        valid_image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']
        
        print(f"Social media upload - File: {file.filename}, extension: {file_extension}")
        
        if file_extension not in valid_image_extensions:
            logger.warning(f"Invalid image format: {file_extension} for file {file.filename}")
            return FileUploadResponse(
                success=False,
                message=f"Invalid image format. Supported formats: {', '.join(valid_image_extensions)}",
                file_ids=[]
            )
        
        # Validate file size
        file_content = await file.read()
        file_size = len(file_content)
        
        print(f"Social media upload - File size: {file_size} bytes")
        
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"File too large: {file_size} bytes for file {file.filename}")
            return FileUploadResponse(
                success=False,
                message=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE} bytes",
                file_ids=[]
            )
        
        # Generate a unique filename to avoid conflicts
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{file.filename}"
        file_path = os.path.join(user_dir, unique_filename)
        
        print(f"Social media upload - Generated file path: {file_path}")
        
        # Save file
        try:
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            print(f"Social media upload - File successfully written to: {file_path}")
            
            # Verify file was actually written
            if os.path.exists(file_path):
                file_stat = os.stat(file_path)
                print(f"Social media upload - File exists on disk, size: {file_stat.st_size} bytes")
            else:
                print(f"Social media upload - WARNING: File does not exist after write attempt: {file_path}")
        except Exception as write_error:
            print(f"Social media upload - ERROR writing file: {write_error}")
            raise
        
        logger.info(f"Social media image uploaded: {file_path}")
        
        # Return the complete file path to be used directly by social_media_tools.py
        return FileUploadResponse(
            success=True,
            message=f"Successfully uploaded image for social media posting",
            file_ids=[file_path]  # Return the full file path
        )
        
    except Exception as e:
        logger.error(f"Error uploading social media image: {e}")
        return FileUploadResponse(
            success=False,
            message=f"Error uploading image: {str(e)}",
            file_ids=[]
        )

# NOTE: File-related REST endpoints for listing and deletion have been removed.
# Only file upload endpoint remains as REST API for efficiency reasons.
# All other file operations are now handled via WebSocket connections:
# - READ operations (file listing) via /ws/recall with FILES_LIST message type
# - WRITE operations (file deletion) via /ws/record with FILES_DELETE message type


# NOTE: Response scores update REST endpoint has been removed.
# This functionality should be moved to WebSocket like other operations.
# All operations should use the WebSocket connections:
# - READ operations via /ws/recall
# - WRITE operations via /ws/record


@app.websocket("/ws/record")
async def websocket_record(websocket: WebSocket):
    """
    WebSocket endpoint for WRITE operations (record submissions, file updates/deletions, user facts modifications).
    This endpoint handles all data creation, modification, and deletion operations regardless of data type.
    
    Args:
        websocket: WebSocket connection.
    """
    client_id = str(uuid.uuid4())
    
    # Register message handlers
    async def handle_record_submission(client_id: str, message: dict):
        """Handle record submission messages."""
        try:
            # Extract submission data
            data = message.get("data", {})
            content = data.get("content")
            user_id = data.get("user_id")
            record_type = data.get("record_type")
            metadata = data.get("metadata", {})
            
            if not all([content, user_id, record_type]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: content, user_id, or record_type"}
                )
                return
            
            # Create the data package
            data_package = DataPackage(
                user_id=user_id,
                operation_type=OperationType.RECORD,
                data_type=DataType.TEXT,  # For now, only handling text
                text_content=content,
                metadata=metadata
            )
            
            # Define message callback
            async def message_callback(message: dict):
                """Callback to send messages to the client."""
                await websocket_handler.message_service.send_message(
                    client_id,
                    message["type"],
                    message["data"]
                )
            
            # Process the record operation with the message callback
            try:
                response = await conductor_agent.process_record_operation(data_package, message_callback)
                if not isinstance(response, RecordResponse):
                    response = RecordResponse(
                        success=True,
                        message="Successfully recorded submission"
                    )
            except Exception as e:
                print(f"Error in process_record_operation: {e}")
                response = RecordResponse(
                    success=False,
                    message=f"Error processing submission: {str(e)}"
                )
            
            # Send the final response back to the client
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.RECORD_RESPONSE,
                response.dict()
            )
            
        except Exception as e:
            print(f"Error in handle_record_submission: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error processing submission: {str(e)}"}
            )
    
    async def handle_record_update_text(client_id: str, message: dict):
        """Handle file text content update messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            file_id = data.get("file_id")
            text_content = data.get("text_content")
            
            if not all([user_id, file_id, text_content is not None]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id, file_id, and text_content"}
                )
                return
            
            # Get the file info to verify it exists and belongs to the user
            file_info = file_db.get_file(file_id, user_id)
            if not file_info:
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": f"File with ID {file_id} not found for user {user_id}"}
                )
                return
            
            # Update the file text content
            success = file_db.update_file_text_content(file_id, text_content, user_id)
            
            # Trigger vectorization if text update was successful
            vectorization_result = False
            if success:
                try:
                    # Initialize vectorizer
                    from app.utils.file_vectorizer import FileVectorizer
                    vectorizer = FileVectorizer(user_id)
                    
                    # First delete existing vectors
                    print(f"[VECTOR DEBUG] Deleting existing vectors for file {file_id} after text update via WebSocket")
                    deletion_success = vectorizer.delete_existing_vectors(file_id)
                    print(f"[VECTOR DEBUG] Deletion of existing vectors for file {file_id}: {deletion_success}")
                    
                    # Then create new vectors
                    print(f"[VECTOR DEBUG] Starting vectorization for updated content via WebSocket: file_id={file_id}")
                    print(f"[VECTOR DEBUG] Text content length: {len(text_content) if text_content else 0}")
                    
                    vectorization_result = vectorizer.vectorize_file(
                        file_id, 
                        text_content, 
                        file_info
                    )
                    print(f"[VECTOR DEBUG] File vectorization result for WebSocket updated content: {vectorization_result}")
                    
                    if not vectorization_result:
                        # Only update status if vectorization failed
                        print(f"[VECTOR DEBUG] Updating file status to 'vectorization_error' for file_id={file_id}")
                        file_db.update_file_status(file_id, "vectorization_error", user_id)
                except Exception as ve:
                    print(f"[VECTOR DEBUG] Error vectorizing updated file content via WebSocket for {file_id}: {str(ve)}")
                    import traceback
                    print(f"[VECTOR DEBUG] Traceback: {traceback.format_exc()}")
                    file_db.update_file_status(file_id, "vectorization_error", user_id)
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.RECORD_RESPONSE,
                {
                    "success": success,
                    "vectorization_success": vectorization_result if success else False,
                    "message": "Successfully updated file text content and vectors" if (success and vectorization_result) 
                              else "Successfully updated file text content but vectorization failed" if (success and not vectorization_result)
                              else f"Error updating text content for file {file_id}",
                    "file_id": file_id
                }
            )
            
        except Exception as e:
            print(f"Error in handle_record_update_text: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error updating file text content: {str(e)}"}
            )
    
    # User Facts WRITE Handlers (Moved from /ws/recall endpoint)
    async def handle_user_facts_add(client_id: str, message: dict):
        """Handle add user fact messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            fact = data.get("fact")
            category = data.get("category")
            source_text = data.get("source_text")
            confidence = data.get("confidence")
            
            if not all([user_id, fact]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and fact"}
                )
                return
            
            # Add user fact
            new_fact = user_facts_db.add_fact(
                fact=fact,
                category=category,
                source_text=source_text,
                confidence=confidence,
                user_id=user_id
            )
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": True,
                    "message": "Successfully added user fact",
                    "fact": new_fact
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_add: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error adding user fact: {str(e)}"}
            )
    
    async def handle_user_facts_update(client_id: str, message: dict):
        """Handle update user fact messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            fact_id = data.get("fact_id")
            updates = data.get("updates", {})
            
            if not all([user_id, fact_id, updates]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id, fact_id, and updates"}
                )
                return
            
            # Update user fact
            updated_fact = user_facts_db.update_fact(fact_id=fact_id, updates=updates, user_id=user_id)
            
            if not updated_fact:
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.USER_FACTS_RESPONSE,
                    {
                        "success": False,
                        "message": f"Fact with ID {fact_id} not found"
                    }
                )
                return
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": True,
                    "message": "Successfully updated user fact",
                    "fact": updated_fact
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_update: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error updating user fact: {str(e)}"}
            )
    
    async def handle_user_facts_delete(client_id: str, message: dict):
        """Handle delete user fact messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            fact_id = data.get("fact_id")
            
            if not all([user_id, fact_id]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and fact_id"}
                )
                return
            
            # Delete user fact
            success = user_facts_db.delete_fact(fact_id=fact_id, user_id=user_id)
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.USER_FACTS_RESPONSE,
                {
                    "success": success,
                    "message": "Successfully deleted user fact" if success else f"Fact with ID {fact_id} not found"
                }
            )
            
        except Exception as e:
            print(f"Error in handle_user_facts_delete: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error deleting user fact: {str(e)}"}
            )
    
    async def handle_files_delete(client_id: str, message: dict):
        """Handle file delete messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            file_id = data.get("file_id")
            
            if not all([user_id, file_id]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and file_id"}
                )
                return
            
            # First, delete associated vectors BEFORE deleting the file
            # This ensures we can still access the vector IDs in the file metadata
            vectors_deleted = False
            try:
                # Import here to avoid circular imports
                from app.utils.file_vectorizer import FileVectorizer
                import traceback
                import logging
                
                logger = logging.getLogger(__name__)
                
                logger.info(f"[VECTOR DEBUG] Attempting to delete vectors for file {file_id} BEFORE file deletion")
                print(f"[VECTOR DEBUG] Attempting to delete vectors for file {file_id} BEFORE file deletion")
                
                # We're now using the file metadata to track vectors in the related_vectors field
                logger.info(f"[VECTOR DEBUG] Checking file metadata for vectors associated with file_id={file_id}")
                print(f"[VECTOR DEBUG] Checking file metadata for vectors associated with file_id={file_id}")
                
                # Delete vectors for the file
                vectorizer = FileVectorizer(user_id)
                vectors_deleted = vectorizer.delete_existing_vectors(file_id)
                
                logger.info(f"[VECTOR DEBUG] Vectors deleted for file {file_id}: {vectors_deleted}")
                print(f"[VECTOR DEBUG] Vectors deleted for file {file_id}: {vectors_deleted}")
            except Exception as e:
                logger.error(f"[VECTOR DEBUG] Error deleting vectors for file {file_id}: {str(e)}")
                print(f"[VECTOR DEBUG] Error deleting vectors for file {file_id}: {str(e)}")
                logger.error(f"[VECTOR DEBUG] Traceback: {traceback.format_exc()}")
                print(f"[VECTOR DEBUG] Traceback: {traceback.format_exc()}")
            
            # Now delete the file after vectors have been deleted
            success = file_db.delete_file(file_id=file_id, user_id=user_id)
            
            # Log the result of file deletion
            if success:
                logger.info(f"[VECTOR DEBUG] File {file_id} deleted successfully after vector deletion")
                print(f"[VECTOR DEBUG] File {file_id} deleted successfully after vector deletion")
            else:
                logger.warning(f"[VECTOR DEBUG] Failed to delete file {file_id} after vector deletion")
                print(f"[VECTOR DEBUG] Failed to delete file {file_id} after vector deletion")
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.FILES_RESPONSE,
                {
                    "success": success,
                    "message": "Successfully deleted file" if success else f"File with ID {file_id} not found",
                    "vectors_deleted": vectors_deleted if success else False
                }
            )
            
        except Exception as e:
            print(f"Error in handle_files_delete: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error deleting file: {str(e)}"}
            )
    
    async def handle_files_transcribe(client_id: str, message: dict):
        """Handle file transcription messages."""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            file_id = data.get("file_id")
            
            if not all([user_id, file_id]):
                await websocket_handler.message_service.send_message(
                    client_id,
                    MessageType.STATUS_UPDATE,
                    {"message": "Missing required fields: user_id and file_id"}
                )
                return
            
            # Update status to processing
            file_db.update_file_status(file_id=file_id, status="processing", user_id=user_id)
            
            # Send initial status update
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Starting transcription for file {file_id}"}
            )
            
            # Process file in background
            success = await file_processor.process_file(file_id, user_id)
            
            # Send response
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.FILES_RESPONSE,
                {
                    "success": success,
                    "message": "Successfully transcribed file" if success else f"Error transcribing file {file_id}"
                }
            )
            
        except Exception as e:
            print(f"Error in handle_files_transcribe: {e}")
            await websocket_handler.message_service.send_message(
                client_id,
                MessageType.STATUS_UPDATE,
                {"message": f"Error transcribing file: {str(e)}"}
            )
    
    # Register the record (WRITE) operation handlers
    websocket_handler.message_service.register_handler(MessageType.RECORD_SUBMISSION, handle_record_submission)
    websocket_handler.message_service.register_handler(MessageType.RECORD_UPDATE_TEXT, handle_record_update_text)
    
    # Register file WRITE operations handlers
    websocket_handler.message_service.register_handler(MessageType.FILES_DELETE, handle_files_delete)
    websocket_handler.message_service.register_handler(MessageType.FILES_TRANSCRIBE, handle_files_transcribe)
    
    # Register user facts WRITE operation handlers
    websocket_handler.message_service.register_handler(MessageType.USER_FACTS_ADD, handle_user_facts_add)
    websocket_handler.message_service.register_handler(MessageType.USER_FACTS_UPDATE, handle_user_facts_update)
    websocket_handler.message_service.register_handler(MessageType.USER_FACTS_DELETE, handle_user_facts_delete)
    
    # Handle the connection
    await websocket_handler.handle_connection(websocket, client_id)


# The /ws/user-facts WebSocket endpoint has been removed
# User facts operations are now handled through the /ws/recall endpoint


# The /ws/files WebSocket endpoint has been removed
# File operations are now handled through the /ws/record endpoint


if __name__ == "__main__":
    # Run the API server
    uvicorn.run(app, host=API_HOST, port=API_PORT)
