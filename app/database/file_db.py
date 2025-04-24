#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
File Database Interface for managing uploaded files.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from app.core.config import FILE_DB_PATH

logger = logging.getLogger(__name__)

class FileDBInterface:
    """Interface for storing and managing file metadata."""

    def __init__(self, user_id: str, db_path: str = FILE_DB_PATH):
        """Initialize the FileDBInterface.
        
        Args:
            user_id: ID of the user whose files are being managed.
                    A user-specific subdirectory will be created.
            db_path: Path to the file database.
        """
        self.user_id = user_id
        self.db_path = db_path
        
        # Create user-specific directory
        self.user_dir = os.path.join(self.db_path, user_id)
        os.makedirs(self.user_dir, exist_ok=True)
    
    def _resolve_user_id(self, user_id: Optional[str] = None) -> str:
        """Helper method to resolve the user ID for database operations.
        
        This standardizes user ID handling across all methods,
        enforcing the application's user-ID-based architecture.
        
        Args:
            user_id: Optional user ID to override the instance user_id.
        
        Returns:
            The resolved user ID (either from parameter or instance).
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        resolved_id = user_id if user_id is not None else self.user_id
        if not resolved_id:
            raise ValueError("User ID is required for this operation. Please provide a user ID.")
        return resolved_id
    
    def _get_user_metadata_file(self, user_id: Optional[str] = None) -> str:
        """Get the path to a user's metadata file.
        
        Args:
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            Path to the user's metadata file
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        resolved_id = self._resolve_user_id(user_id)
        user_dir = os.path.join(self.db_path, resolved_id)
        os.makedirs(user_dir, exist_ok=True)
        return os.path.join(user_dir, "file_metadata.json")
    
    def _load_metadata(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load the file metadata from JSON file for a specific user.
        
        Args:
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            List of file metadata dictionaries.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        resolved_id = self._resolve_user_id(user_id)
        metadata_file = self._get_user_metadata_file(resolved_id)
        try:
            if os.path.exists(metadata_file):
                with open(metadata_file, "r") as f:
                    return json.load(f)
            else:
                # Create empty metadata file
                self._save_metadata(resolved_id, [])
                return []
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading metadata for user {resolved_id}: {e}")
            return []
    
    def _save_metadata(self, user_id: Optional[str] = None, metadata_list: List[Dict[str, Any]] = None) -> None:
        """Save the file metadata to JSON file for a specific user.
        
        Args:
            user_id: Optional user ID to override the instance user_id.
            metadata_list: List of file metadata dictionaries.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        resolved_id = self._resolve_user_id(user_id)
        metadata_file = self._get_user_metadata_file(resolved_id)
        try:
            with open(metadata_file, "w") as f:
                json.dump(metadata_list, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata for user {resolved_id}: {e}")
            raise
    
    def add_file(self, 
                 file_name: str,
                 file_path: str,
                 file_type: str,
                 file_size: int,
                 user_id: Optional[str] = None,
                 processing_status: str = "pending") -> str:
        """Add a new file to the database.
        
        Args:
            file_name: Name of the file
            file_path: Path where the file is stored
            file_type: MIME type of the file
            file_size: Size of the file in bytes
            user_id: Optional user ID to override the instance user_id
            processing_status: Current processing status of the file
            
        Returns:
            file_id: The ID of the newly added file
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        # Resolve the user ID
        resolved_id = self._resolve_user_id(user_id)
        
        # Generate a unique ID for the file
        file_id = str(uuid.uuid4())
        
        # Create the file metadata object with simplified structure
        file_metadata = {
            "id": file_id,
            "file_name": file_name,
            "file_path": file_path,
            "file_type": file_type,
            "file_size": file_size,
            "user_id": resolved_id,
            "processing_status": processing_status,
            "upload_date": datetime.now().isoformat()
        }
        
        # Add the file metadata to the user's JSON file
        metadata_list = self._load_metadata(resolved_id)
        metadata_list.append(file_metadata)
        self._save_metadata(resolved_id, metadata_list)
        
        return file_id
    
    def get_file(self, file_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get file metadata by ID.
        
        Args:
            file_id: The ID of the file to retrieve.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            The file metadata object if found, None otherwise.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        # Try to resolve the user ID, but don't raise an error if it's None
        # This allows searching across all users if no user_id is provided
        try:
            resolved_id = self._resolve_user_id(user_id)
            # If user_id is resolved, search only in that user's metadata
            metadata_list = self._load_metadata(resolved_id)
            for metadata in metadata_list:
                if metadata["id"] == file_id:
                    return metadata
        except ValueError:
            # If no user_id is available, search across all users
            # This is less efficient but necessary for backward compatibility
            user_dirs = [d for d in os.listdir(self.db_path) 
                        if os.path.isdir(os.path.join(self.db_path, d)) and d != "uploads"]
            
            for user_dir in user_dirs:
                try:
                    metadata_list = self._load_metadata(user_dir)
                    for metadata in metadata_list:
                        if metadata["id"] == file_id:
                            return metadata
                except Exception as e:
                    logger.error(f"Error loading metadata for user {user_dir}: {e}")
                        
        return None
    
    def get_user_files(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all files for a user.
        
        Args:
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            List of file metadata objects.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        # Resolve the user ID
        resolved_id = self._resolve_user_id(user_id)
        
        # Load metadata for the resolved user ID
        metadata_list = self._load_metadata(resolved_id)
        
        # Check if user has actual files not in metadata
        # This helps recover from metadata inconsistencies
        user_dir = os.path.join(self.db_path, resolved_id)
        if os.path.exists(user_dir):
            file_paths = [os.path.join(user_dir, f) for f in os.listdir(user_dir) 
                        if os.path.isfile(os.path.join(user_dir, f)) and f != "file_metadata.json"]
            
            # Check which files are not in metadata
            tracked_paths = {metadata["file_path"] for metadata in metadata_list}
            untracked_files = [path for path in file_paths if path not in tracked_paths]
            
            # Add untracked files to metadata
            for file_path in untracked_files:
                file_name = os.path.basename(file_path)
                # Try to determine file type, default to text/plain
                file_type = "text/plain"  # Default
                if file_name.endswith('.pdf'):
                    file_type = "application/pdf"
                elif file_name.endswith('.txt'):
                    file_type = "text/plain"
                elif file_name.endswith('.md'):
                    file_type = "text/markdown"
                
                file_size = os.path.getsize(file_path)
                
                logger.info(f"Adding untracked file to metadata: {file_path}")
                self.add_file(
                    file_name=file_name,
                    file_path=file_path,
                    file_type=file_type,
                    file_size=file_size,
                    user_id=resolved_id,
                    processing_status="complete"  # Assume existing files are processed
                )
            
            # Reload metadata if we added new files
            if untracked_files:
                metadata_list = self._load_metadata(resolved_id)
        
        return metadata_list
    
    def update_file_status(self, file_id: str, status: str, user_id: Optional[str] = None) -> bool:
        """Update the processing status of a file.
        
        Args:
            file_id: The ID of the file to update.
            status: The new processing status.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            True if the file was updated, False otherwise.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        try:
            # Try to resolve the user ID
            resolved_id = self._resolve_user_id(user_id)
            
            # Load metadata for the resolved user ID
            metadata_list = self._load_metadata(resolved_id)
            
            # Update the file status
            for metadata in metadata_list:
                if metadata["id"] == file_id:
                    metadata["processing_status"] = status
                    metadata["updated_at"] = datetime.now().isoformat()
                    self._save_metadata(resolved_id, metadata_list)
                    return True
                    
            # If we didn't find the file with the resolved user ID, try to find it by file ID only
            if not user_id:  # Only do this if user_id wasn't explicitly provided
                file_metadata = self.get_file(file_id)
                if file_metadata:
                    alt_user_id = file_metadata.get("user_id")
                    if alt_user_id and alt_user_id != resolved_id:
                        # Try updating with the found user ID
                        metadata_list = self._load_metadata(alt_user_id)
                        for metadata in metadata_list:
                            if metadata["id"] == file_id:
                                metadata["processing_status"] = status
                                metadata["updated_at"] = datetime.now().isoformat()
                                self._save_metadata(alt_user_id, metadata_list)
                                return True
        except ValueError:
            # If no user_id is available, try to find the file by ID only
            file_metadata = self.get_file(file_id)
            if file_metadata:
                alt_user_id = file_metadata.get("user_id")
                if alt_user_id:
                    # Try updating with the found user ID
                    metadata_list = self._load_metadata(alt_user_id)
                    for metadata in metadata_list:
                        if metadata["id"] == file_id:
                            metadata["processing_status"] = status
                            metadata["updated_at"] = datetime.now().isoformat()
                            self._save_metadata(alt_user_id, metadata_list)
                            return True
                    
        return False
        
    def update_file_text_content(self, file_id: str, text_content: str, user_id: Optional[str] = None) -> bool:
        """Update the text content of a file in the metadata.
        
        Args:
            file_id: The ID of the file to update.
            text_content: The extracted text content to store.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            True if the file was updated, False otherwise.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        try:
            # Try to resolve the user ID
            resolved_id = self._resolve_user_id(user_id)
            
            # Load metadata for the resolved user ID
            metadata_list = self._load_metadata(resolved_id)
            
            # Update the file text content
            for metadata in metadata_list:
                if metadata["id"] == file_id:
                    # Add or update the text_content field
                    metadata["text_content"] = text_content
                    metadata["updated_at"] = datetime.now().isoformat()
                    self._save_metadata(resolved_id, metadata_list)
                    return True
                    
            # If we didn't find the file with the resolved user ID, try to find it by file ID only
            if not user_id:  # Only do this if user_id wasn't explicitly provided
                file_metadata = self.get_file(file_id)
                if file_metadata:
                    alt_user_id = file_metadata.get("user_id")
                    if alt_user_id and alt_user_id != resolved_id:
                        # Try updating with the found user ID
                        metadata_list = self._load_metadata(alt_user_id)
                        for metadata in metadata_list:
                            if metadata["id"] == file_id:
                                metadata["text_content"] = text_content
                                metadata["updated_at"] = datetime.now().isoformat()
                                self._save_metadata(alt_user_id, metadata_list)
                                return True
        except ValueError:
            # If no user_id is available, try to find the file by ID only
            file_metadata = self.get_file(file_id)
            if file_metadata:
                alt_user_id = file_metadata.get("user_id")
                if alt_user_id:
                    # Try updating with the found user ID
                    metadata_list = self._load_metadata(alt_user_id)
                    for metadata in metadata_list:
                        if metadata["id"] == file_id:
                            metadata["text_content"] = text_content
                            metadata["updated_at"] = datetime.now().isoformat()
                            self._save_metadata(alt_user_id, metadata_list)
                            return True
                    
        return False
    
    def delete_file(self, file_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a file and its metadata.
        
        Args:
            file_id: The ID of the file to delete.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            True if the file was deleted, False otherwise.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        try:
            # Try to resolve the user ID
            resolved_id = self._resolve_user_id(user_id)
            
            # Load metadata for the resolved user ID
            metadata_list = self._load_metadata(resolved_id)
            
            # Delete the file
            for i, metadata in enumerate(metadata_list):
                if metadata["id"] == file_id:
                    # Remove the file from disk
                    try:
                        if os.path.exists(metadata["file_path"]):
                            os.remove(metadata["file_path"])
                    except Exception as e:
                        logger.error(f"Error deleting file from disk: {e}")
                    
                    # Remove the metadata from the list
                    metadata_list.pop(i)
                    self._save_metadata(resolved_id, metadata_list)
                    return True
                    
            # If we didn't find the file with the resolved user ID, try to find it by file ID only
            if not user_id:  # Only do this if user_id wasn't explicitly provided
                file_metadata = self.get_file(file_id)
                if file_metadata:
                    alt_user_id = file_metadata.get("user_id")
                    if alt_user_id and alt_user_id != resolved_id:
                        # Try deleting with the found user ID
                        metadata_list = self._load_metadata(alt_user_id)
                        for i, metadata in enumerate(metadata_list):
                            if metadata["id"] == file_id:
                                # Remove the file from disk
                                try:
                                    if os.path.exists(metadata["file_path"]):
                                        os.remove(metadata["file_path"])
                                except Exception as e:
                                    logger.error(f"Error deleting file from disk: {e}")
                                
                                # Remove the metadata from the list
                                metadata_list.pop(i)
                                self._save_metadata(alt_user_id, metadata_list)
                                return True
        except ValueError:
            # If no user_id is available, try to find the file by ID only
            file_metadata = self.get_file(file_id)
            if file_metadata:
                alt_user_id = file_metadata.get("user_id")
                if alt_user_id:
                    # Try deleting with the found user ID
                    metadata_list = self._load_metadata(alt_user_id)
                    for i, metadata in enumerate(metadata_list):
                        if metadata["id"] == file_id:
                            # Remove the file from disk
                            try:
                                if os.path.exists(metadata["file_path"]):
                                    os.remove(metadata["file_path"])
                            except Exception as e:
                                logger.error(f"Error deleting file from disk: {e}")
                            
                            # Remove the metadata from the list
                            metadata_list.pop(i)
                            self._save_metadata(alt_user_id, metadata_list)
                            return True
                    
        return False
        
    def list_files(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Alias for get_user_files to match the API naming convention.
        
        Args:
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            List of file metadata objects.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        return self.get_user_files(user_id)
        
    def save_file(self, file_name: str, file_content: bytes, file_type: str, user_id: Optional[str] = None) -> str:
        """Save a file to the user's directory and add it to the database.
        
        Args:
            file_name: Name of the file
            file_content: Binary content of the file
            file_type: MIME type of the file
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            file_id: The ID of the newly added file
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        # Resolve the user ID
        resolved_id = self._resolve_user_id(user_id)
        
        # Create user directory if it doesn't exist
        user_dir = os.path.join(self.db_path, resolved_id)
        os.makedirs(user_dir, exist_ok=True)
        
        # Save file to disk
        file_path = os.path.join(user_dir, file_name)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Add file to database
        file_id = self.add_file(
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=len(file_content),
            user_id=resolved_id,
            processing_status="complete"  # Mark as complete since we're not processing it
        )
        
        return file_id
    


    # Create a method to get the text content of a file from the file_metadata.json file
    def get_file_text_content(self, file_id: str, user_id: Optional[str] = None) -> str:
        """Get the text content of a file from the file_metadata.json file.
        
        Args:
            file_id: The ID of the file to get the text content of.
            user_id: Optional user ID to override the instance user_id."""
        
        # Resolve the user ID
        resolved_id = self._resolve_user_id(user_id)
        
        # Load metadata for the resolved user ID
        metadata_list = self._load_metadata(resolved_id)

        # Get the text content of the file
        for metadata in metadata_list:
            if metadata["id"] == file_id:
                return metadata["text_content"]
        
        return None
    