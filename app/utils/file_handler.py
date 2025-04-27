#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
File handling utilities for the Move 37 application.
"""

import base64
import os
from typing import Dict, Optional, List, Any
from datetime import datetime
import uuid
import json
from pathlib import Path
import logging
from fastapi import WebSocket

from app.database.file_db import FileDBInterface
from app.core.config import FILE_DB_PATH, MAX_FILE_SIZE, ALLOWED_FILE_TYPES
from app.models.messages import MessageType
from app.utils.file_vectorizer import FileVectorizer

logger = logging.getLogger(__name__)

class FileUploadManager:
    def __init__(self):
        """Initialize the FileUploadManager."""
        self.db_path = Path(FILE_DB_PATH)
        self.active_uploads = {}
        # Use the same default user ID as in main.py for consistency
        DEFAULT_USER_ID = "default"
        self.file_db = FileDBInterface(user_id=DEFAULT_USER_ID)
        logger.info(f"FileUploadManager initialized with base directory: {self.db_path}")
        
    async def handle_file_message(self, message: Dict, websocket: WebSocket) -> Dict:
        """Handle incoming file-related WebSocket messages."""
        msg_type = message.get('type')
        logger.info(f"Handling file message of type: {msg_type}")
        
        # Use MessageType enum values directly for consistency
        handlers = {
            MessageType.FILES_LIST.value: self.handle_file_list_request,
            MessageType.FILES_DELETE.value: self.handle_file_delete,
            MessageType.FILES_UPLOAD.value: self.handle_file_upload
        }
        
        handler = handlers.get(msg_type)
        if not handler:
            logger.error(f"Invalid file message type: {msg_type}")
            return {
                'type': MessageType.STATUS_UPDATE.value, 
                'data': {'message': 'Invalid file message type'}
            }
            
        try:
            logger.debug(f"Processing message data: {message.get('data', {})}")
            response = await handler(message.get('data', {}), websocket)
            logger.debug(f"Handler response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error handling file message: {e}", exc_info=True)
            return {
                'type': MessageType.STATUS_UPDATE.value, 
                'data': {'message': str(e)}
            }
    
    async def handle_file_list_request(self, data: Dict, websocket: WebSocket) -> Dict:
        """Handle file list request."""
        try:
            user_id = data.get('user_id')
            
            if not user_id:
                return {
                    'type': MessageType.STATUS_UPDATE.value,
                    'data': {'message': 'Missing required field: user_id'}
                }
            
            # Get files for user
            files = self.file_db.get_user_files(user_id)
            
            # Return response using MessageType enum for consistency
            return {
                'type': MessageType.FILES_RESPONSE.value,  # Use the enum value for consistency
                'data': {
                    'success': True,
                    'message': f"Found {len(files)} files",
                    'files': files
                }
            }
        except Exception as e:
            logger.error(f"Error handling file list request: {e}", exc_info=True)
            return {
                'type': MessageType.STATUS_UPDATE.value,
                'data': {'message': f"Error listing files: {str(e)}"}
            }
    
    async def handle_file_delete(self, data: Dict, websocket: WebSocket) -> Dict:
        """Handle file delete request."""
        try:
            user_id = data.get('user_id')
            file_id = data.get('file_id')
            
            if not all([user_id, file_id]):
                return {
                    'type': MessageType.STATUS_UPDATE.value,
                    'data': {'message': 'Missing required fields: user_id and file_id'}
                }
            
            # First, delete the associated vectors
            try:
                # Initialize the FileVectorizer with the user_id
                vectorizer = FileVectorizer(user_id)
                
                # Delete the vectors associated with the file
                vector_deletion_success = vectorizer.delete_existing_vectors(file_id)
                logger.info(f"Vector deletion for file {file_id}: {vector_deletion_success}")
            except Exception as vector_error:
                logger.error(f"Error deleting vectors for file {file_id}: {vector_error}", exc_info=True)
                # Continue with file deletion even if vector deletion fails
            
            # Delete file - pass the user_id to ensure proper user isolation
            success = self.file_db.delete_file(file_id, user_id)
            
            # Return response using MessageType enum for consistency
            return {
                'type': MessageType.FILES_RESPONSE.value,
                'data': {
                    'success': success,
                    'message': "File deleted successfully" if success else "Failed to delete file"
                }
            }
        except Exception as e:
            logger.error(f"Error handling file delete request: {e}", exc_info=True)
            return {
                'type': MessageType.STATUS_UPDATE.value,
                'data': {'message': f"Error deleting file: {str(e)}"}
            }
    
    async def handle_file_upload(self, data: Dict, websocket: WebSocket) -> Dict:
        """Handle file upload request."""
        try:
            user_id = data.get('user_id')
            file_data = data.get('file', {})
            
            if not all([user_id, file_data]):
                return {
                    'type': 'error',
                    'data': {'error': 'Missing required fields: user_id and file data'}
                }
            
            file_name = file_data.get('name')
            file_type = file_data.get('type')
            file_content_base64 = file_data.get('content')
            
            if not all([file_name, file_content_base64]):
                return {
                    'type': 'error',
                    'data': {'error': 'Missing required file fields: name and content'}
                }
            
            # Decode base64 content
            file_content = base64.b64decode(file_content_base64)
            
            # Check file size
            if len(file_content) > MAX_FILE_SIZE:
                return {
                    'type': 'error',
                    'data': {'error': f"File size ({len(file_content)} bytes) exceeds maximum allowed size ({MAX_FILE_SIZE} bytes)"}
                }
            
            # Check file type if specified
            if ALLOWED_FILE_TYPES and file_type not in ALLOWED_FILE_TYPES:
                return {
                    'type': 'error',
                    'data': {'error': f"File type {file_type} is not allowed"}
                }
            
            # Create user directory if it doesn't exist
            user_dir = self.db_path / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # Save file to disk
            file_path = user_dir / file_name
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Add file to database
            file_id = self.file_db.add_file(
                file_name=file_name,
                file_path=str(file_path),
                file_type=file_type,
                file_size=len(file_content),
                user_id=user_id
            )
            
            # Return success response
            return {
                'type': 'file_upload_response',
                'data': {
                    'success': True,
                    'message': "File uploaded successfully",
                    'file_id': file_id
                }
            }
        except Exception as e:
            logger.error(f"Error handling file upload: {e}", exc_info=True)
            return {
                'type': 'error',
                'data': {'error': f"Error uploading file: {str(e)}"}
            }
