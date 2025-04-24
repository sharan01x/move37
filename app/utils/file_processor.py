#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
File processing utilities for the LifeScribe application.

This module provides utilities for processing uploaded files,
including text extraction, transcription, and vectorization for semantic search.
"""

import asyncio
import logging
import traceback
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.database.file_db import FileDBInterface
from app.utils.transcription import TranscriptionUtil
from app.utils.file_vectorizer import FileVectorizer

logger = logging.getLogger(__name__)
# Set logging level to DEBUG for this module
logger.setLevel(logging.DEBUG)

class FileProcessor:
    """Utility for processing files asynchronously."""
    
    def __init__(self, file_db: FileDBInterface):
        """Initialize the FileProcessor.
        
        Args:
            file_db: File database interface for updating file metadata.
        """
        self.file_db = file_db
        
    async def process_file(self, file_id: str, user_id: str) -> bool:
        """
        Process a file asynchronously, extracting text content and updating metadata.
        
        Args:
            file_id: ID of the file to process.
            user_id: ID of the user who owns the file.
            
        Returns:
            True if processing was successful, False otherwise.
        """
        logger.debug(f"Starting file processing for file_id={file_id}, user_id={user_id}")
        try:
            # Get file metadata
            logger.debug(f"Retrieving file metadata for file_id={file_id}")
            file_metadata = self.file_db.get_file(file_id, user_id)
            if not file_metadata:
                logger.error(f"File not found: {file_id}")
                return False
                
            logger.debug(f"File metadata retrieved: {file_metadata}")
            file_path = file_metadata.get("file_path")
            file_type = file_metadata.get("file_type")
            
            if not file_path:
                logger.error(f"File path not found in metadata: {file_id}")
                return False
                
            # Update status to processing
            logger.debug(f"Updating file status to 'processing' for file_id={file_id}")
            self.file_db.update_file_status(file_id, "processing", user_id)
            
            # Extract text from file
            logger.debug(f"Extracting text from file: {file_path} with type: {file_type}")
            text_content, status = TranscriptionUtil.extract_text_from_file(file_path, file_type)
            logger.debug(f"Text extraction complete. Status: {status}, Content length: {len(text_content) if text_content else 0}")
            
            # Update file metadata with text content
            if text_content:
                logger.debug(f"Updating file metadata with extracted text content for file_id={file_id}")
                success = self.file_db.update_file_text_content(file_id, text_content, user_id)
                logger.debug(f"Text content update result: {success}")
                
                # Vectorize the file content for semantic search
                logger.debug(f"Vectorizing file content for file_id={file_id}")
                try:
                    # FUTURE IMPROVEMENT: For very large files, implement a queuing system
                    # that processes vectorization in a separate worker to avoid blocking
                    # the main processing thread and to handle memory constraints
                    vectorizer = FileVectorizer(user_id)
                    vectorization_success = vectorizer.vectorize_file(
                        file_id, 
                        text_content, 
                        file_metadata
                    )
                    logger.debug(f"File vectorization result: {vectorization_success}")
                    
                    # Update file status to complete after successful vectorization
                    if vectorization_success:
                        logger.debug(f"Updating file status to 'complete' for file_id={file_id}")
                        self.file_db.update_file_status(file_id, "complete", user_id)
                    else:
                        logger.error(f"Vectorization failed for file_id={file_id}")
                        self.file_db.update_file_status(file_id, "vectorization_error", user_id)
                except Exception as e:
                    logger.error(f"Error vectorizing file {file_id}: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    # Update status to vectorization_error
                    logger.debug(f"Updating file status to 'vectorization_error' for file_id={file_id}")
                    self.file_db.update_file_status(file_id, "vectorization_error", user_id)
            else:
                logger.warning(f"No text content extracted from file: {file_path}")
                
                # Only update status if no text content was extracted and we haven't already set a status
                logger.debug(f"Updating file status to '{status}' for file_id={file_id}")
                self.file_db.update_file_status(file_id, status, user_id)
            
            logger.debug(f"File processing completed successfully for file_id={file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing file {file_id}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Update status to error
            try:
                logger.debug(f"Updating file status to 'transcription_error' for file_id={file_id}")
                self.file_db.update_file_status(file_id, "transcription_error", user_id)
            except Exception as update_error:
                logger.error(f"Failed to update error status: {str(update_error)}")
            return False
            
    async def process_files(self, file_ids: List[str], user_id: str) -> Dict[str, bool]:
        """
        Process multiple files asynchronously.
        
        Args:
            file_ids: List of file IDs to process.
            user_id: ID of the user who owns the files.
            
        Returns:
            Dictionary mapping file IDs to processing success status.
        """
        tasks = []
        for file_id in file_ids:
            task = asyncio.create_task(self.process_file(file_id, user_id))
            tasks.append((file_id, task))
            
        results = {}
        for file_id, task in tasks:
            try:
                results[file_id] = await task
            except Exception as e:
                logger.error(f"Error in task for file {file_id}: {str(e)}")
                results[file_id] = False
                
        return results
