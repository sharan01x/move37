#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
File Search Tool for searching content in user-uploaded files.
This tool extends the functionality of the Librarian Agent to make it accessible via MCP.
"""

import logging
import json
import os
import asyncio
from typing import Dict, Any, List, Optional
import concurrent.futures

from app.agents.librarian_agent import LibrarianAgent

logger = logging.getLogger(__name__)

# Create a singleton instance of the LibrarianAgent to be reused
_librarian_agent = None

def get_librarian_agent():
    """Get or create a singleton instance of LibrarianAgent."""
    global _librarian_agent
    if _librarian_agent is None:
        _librarian_agent = LibrarianAgent()
    return _librarian_agent

class FileSearchToolFunctions:
    """Functions for searching content in user files."""
    
    @staticmethod
    def find_information_within_user_files(query: str, user_id: str) -> Dict[str, Any]:
        """
        Search for the answer to the user's query using the information from the user's files.
        
        Args:
            query: The search query
            user_id: User ID required for authentication
            
        Returns:
            The answer to the user's query as a string.
        """
        try:
            if not user_id:
                logger.error("No user_id provided for file search")
                return {"error": "user_id is required and cannot be empty"}
            
            # Get the librarian agent instance
            librarian = get_librarian_agent()
            
            # Define a synchronous function that will await the async function
            def run_async_query():
                # This function runs in a separate thread where it's safe to create a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        librarian.answer_query_async(query=query, user_id=user_id)
                    )
                finally:
                    loop.close()
            
            # Use a thread executor to run the async function
            with concurrent.futures.ThreadPoolExecutor() as executor:
                response = executor.submit(run_async_query).result()
                
            return response
                
        except Exception as e:
            logger.error(f"Error answering query with file information: {e}", exc_info=True)
            return {"error": f"Error answering query: {str(e)}"}
    
    @staticmethod
    def get_file_content(file_name: str, user_id: str) -> Dict[str, Any]:
        """
        Retrieve the full content of a specific document.
        
        Args:
            file_name: Name of the file to retrieve
            user_id: User ID required for authentication
            
        Returns:
            Dictionary containing the file content and metadata
        """
        try:
            if not user_id:
                logger.error("No user_id provided for get_file_content")
                return {"error": "user_id is required and cannot be empty"}
                
            # Load file metadata
            metadata_file_path = f"data/files/{user_id}/file_metadata.json"
            if not os.path.exists(metadata_file_path):
                logger.warning(f"Metadata file not found: {metadata_file_path}")
                return {"error": "No files found for this user"}
                
            with open(metadata_file_path, 'r') as f:
                all_files_metadata = json.load(f)
            
            # Find the requested file
            file_metadata = None
            for file_data in all_files_metadata:
                if file_data.get('file_name') == file_name:
                    file_metadata = file_data
                    break
            
            if not file_metadata:
                return {"error": f"File '{file_name}' not found"}
            
            # Get the file content
            content = file_metadata.get('text_content', '')
            if not content:
                return {"error": f"No text content available for file '{file_name}'"}
            
            return {
                "file_name": file_name,
                "file_type": file_metadata.get('file_type', 'unknown'),
                "file_size": file_metadata.get('file_size', 0),
                "created_at": file_metadata.get('created_at', ''),
                "content": content
            }
        except Exception as e:
            logger.error(f"Error retrieving document content: {e}", exc_info=True)
            return {"error": f"Error retrieving document content: {str(e)}"}
    
    @staticmethod
    def list_user_files(user_id: str) -> Dict[str, Any]:
        """
        List all files uploaded by a user.
        
        Args:
            user_id: User ID required for authentication
            
        Returns:
            Dictionary containing the list of files and their metadata
        """
        try:
            if not user_id:
                logger.error("No user_id provided for list_user_files")
                return {"error": "user_id is required and cannot be empty"}
                
            # Load file metadata
            metadata_file_path = f"data/files/{user_id}/file_metadata.json"
            if not os.path.exists(metadata_file_path):
                logger.warning(f"Metadata file not found: {metadata_file_path}")
                return {"error": "No files found for this user", "files": []}
                
            with open(metadata_file_path, 'r') as f:
                all_files_metadata = json.load(f)
            
            # Format the file list
            files_list = []
            for file_data in all_files_metadata:
                files_list.append({
                    "file_name": file_data.get('file_name', 'Unknown'),
                    "file_type": file_data.get('file_type', 'unknown'),
                    "file_size": file_data.get('file_size', 0),
                    "created_at": file_data.get('created_at', '')
                })
            
            # Sort by most recent first
            files_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            return {
                "message": f"Found {len(files_list)} files",
                "files": files_list
            }
        except Exception as e:
            logger.error(f"Error listing user files: {e}", exc_info=True)
            return {"error": f"Error listing user files: {str(e)}"} 