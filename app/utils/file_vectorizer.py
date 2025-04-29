# -*- coding: utf-8 -*-

"""
File vectorization utilities for the Move 37 application.

This module provides utilities for vectorizing file content for semantic search.
"""

import os
import uuid
import numpy as np
import logging
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from app.utils.chunking import ChunkingUtil
from app.utils.embeddings import get_embedding
from app.utils.vector_utils import (
    init_faiss_index,
    add_vectors_to_index,
    search_vectors_in_index,
    delete_vectors_from_index
)
from app.core.config import EMBEDDING_MODEL_DIMENSIONS

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Default similarity threshold for semantic chunking
# Can be adjusted based on experimentation
DEFAULT_SEMANTIC_THRESHOLD = 0.85 

class FileVectorizer:
    """Utility for vectorizing file content for semantic search."""
    
    def __init__(self, user_id: str):
        """Initialize the FileVectorizer.
        
        Args:
            user_id: ID of the user who owns the files.
        """
        self.user_id = user_id
        self.vectors_dir = Path(f"data/files/{user_id}/vectors")
        self.vectors_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = Path(f"data/files/{user_id}/file_metadata.json")
        self.index_path = self.vectors_dir / "file_vectors.index"
        self.index = init_faiss_index(EMBEDDING_MODEL_DIMENSIONS, str(self.index_path))
        
        # Check for old mapping file and migrate data if needed
        self._migrate_mapping_data_if_needed()
        
    def _migrate_mapping_data_if_needed(self):
        """Migrate data from the old mapping file to file metadata if needed."""
        old_mapping_file = self.vectors_dir / "file_vector_mapping.json"
        
        if not old_mapping_file.exists():
            return
            
        try:
            
            # Load mapping data
            with open(old_mapping_file, "r") as f:
                mapping_data = json.load(f)
                
            # Skip if empty
            if not mapping_data:
                return
                
            
            # Load metadata
            if not self.metadata_file.exists():
                return
                
            with open(self.metadata_file, "r") as f:
                metadata = json.load(f)
                
            # Update metadata with vector IDs
            updates_count = 0
            for file_id, vector_ids in mapping_data.items():
                for file_entry in metadata:
                    if file_entry.get("id") == file_id:
                        # Add the vector IDs to related_vectors field
                        file_entry["related_vectors"] = vector_ids
                        
                        # Update processing status if needed
                        if file_entry.get("processing_status") == "transcribed":
                            file_entry["processing_status"] = "complete"
                            
                        updates_count += 1
                        break
            
            # Save updated metadata
            if updates_count > 0:
                with open(self.metadata_file, "w") as f:
                    json.dump(metadata, f, indent=2)
                
                
                # Rename the old mapping file
                import os
                backup_path = str(old_mapping_file) + ".bak"
                os.rename(str(old_mapping_file), backup_path)
            else:
                logger.debug(f"[VECTOR DEBUG] No files were updated during migration")
                
        except Exception as e:
            logger.error(f"[VECTOR DEBUG] Error during mapping migration: {str(e)}")
            
    
    def vectorize_file(self, file_id: str, text_content: str, file_metadata: Dict[str, Any]) -> bool:
        """Vectorize file content and store embeddings.
        
        Args:
            file_id: ID of the file.
            text_content: Text content of the file.
            file_metadata: Metadata of the file.
            
        Returns:
            True if vectorization was successful, False otherwise.
        """
        try:
            if not text_content or len(text_content) == 0:
                return False
                
            # First, delete any existing vectors for this file
            deletion_success = self.delete_existing_vectors(file_id)
            logger.debug(f"Deletion of existing vectors for file {file_id}: {deletion_success}")
            
            # Chunk the text content using semantic chunking
            logger.debug(f"Starting semantic chunking for file_id={file_id}")
            try:
                chunks = ChunkingUtil.semantic_chunk_text(
                    text_content, 
                    get_embedding, # Pass the embedding function
                    similarity_threshold=DEFAULT_SEMANTIC_THRESHOLD
                )
                logger.debug(f"Semantic chunking yielded {len(chunks)} chunks for file_id={file_id}")
            except Exception as chunking_error:
                logger.error(f"Error during semantic chunking for file_id={file_id}: {chunking_error}", exc_info=True)
                 # Fallback to simple chunking if semantic chunking fails
                logger.warning(f"Falling back to simple chunking for file_id={file_id}")
                chunks = ChunkingUtil.chunk_text(text_content, chunk_size=1000, overlap=100)
            
            # Generate embeddings for each chunk
            vectors = []
            metadata_list = []
            vector_ids = []
            
            # FUTURE IMPROVEMENT: For very large files, process chunks in batches
            # to avoid memory issues and implement progress tracking
            
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding = get_embedding(chunk["text"])
                vectors.append(embedding)
                
                # Create metadata for the chunk
                chunk_id = str(uuid.uuid4())
                vector_ids.append(chunk_id)
                
                metadata = {
                    "id": chunk_id,
                    "file_id": file_id,
                    "user_id": self.user_id,
                    "chunk_index": i,
                    "chunk_text": chunk["text"],
                    "start": chunk["start"],
                    "end": chunk["end"],
                    "file_name": file_metadata.get("file_name", ""),
                    "file_type": file_metadata.get("file_type", ""),
                    "created_at": datetime.now().isoformat(),
                    "upload_date": file_metadata.get("upload_date", "")
                }
                metadata_list.append(metadata)
            
            if not vectors:
                logger.warning(f"[VECTOR DEBUG] No vectors generated for file_id={file_id}")
                return False
                
            # Convert to numpy array
            vectors_np = np.array(vectors, dtype=np.float32)
            
            # Add vectors to index
            add_vectors_to_index(
                self.index,
                vectors_np,
                metadata_list,
                str(self.vectors_dir),
                str(self.index_path)
            )
            
            # Update mapping file and file metadata
            mapping_success = self._update_mapping(file_id, vector_ids)
            
            if not mapping_success:
                logger.warning(f"[VECTOR DEBUG] Failed to update mapping for file_id={file_id}")
                # Continue anyway since vectors are already in the index
            
            logger.debug(f"[VECTOR DEBUG] Vectorization completed successfully for file_id={file_id}")
            return True
        except Exception as e:
            import traceback
            return False
    
    def delete_existing_vectors(self, file_id: str) -> bool:
        """Delete existing vectors for a file.
        
        Args:
            file_id: ID of the file.
            
        Returns:
            True if vectors were deleted successfully, False otherwise.
        """
        try:
            # Get vector IDs from file metadata
            if not self.metadata_file.exists():
                return True  # Nothing to delete
            
            # Find vector IDs in metadata
            vector_ids = []
            
            with open(self.metadata_file, "r") as f:
                metadata = json.load(f)
            
            # Look for the file and get its vector IDs
            for file_entry in metadata:
                if file_entry.get("id") == file_id:
                    # Check both fields for backward compatibility
                    if "related_vectors" in file_entry:
                        vector_ids = file_entry["related_vectors"]
                    elif "vector_ids" in file_entry:
                        vector_ids = file_entry["vector_ids"]
                    break
            
            if vector_ids:
                
                # Delete vectors from index
                delete_result = delete_vectors_from_index(
                    self.index,
                    vector_ids,
                    str(self.vectors_dir),
                    str(self.index_path)
                )
                
                # Also update the file metadata to remove vector IDs
                if self.metadata_file.exists():
                    try:
                        # Load file metadata
                        with open(self.metadata_file, "r") as f:
                            metadata = json.load(f)
                        
                        # Find and update the file entry
                        file_updated = False
                        for file_entry in metadata:
                            if file_entry.get("id") == file_id:
                                # Check for both fields for backward compatibility
                                if "related_vectors" in file_entry:
                                    vectors_removed = file_entry["related_vectors"]
                                    del file_entry["related_vectors"]
                                    if vectors_removed:
                                        sample = vectors_removed[:3] if len(vectors_removed) > 3 else vectors_removed
                                elif "vector_ids" in file_entry:
                                    vectors_removed = file_entry["vector_ids"]
                                    del file_entry["vector_ids"]
                                    if vectors_removed:
                                        sample = vectors_removed[:3] if len(vectors_removed) > 3 else vectors_removed
                                file_updated = True
                                break
                        
                        if file_updated:
                            # Save updated metadata
                            with open(self.metadata_file, "w") as f:
                                json.dump(metadata, f, indent=2)
                        else:
                            logger.warning(f"File not found in metadata: {file_id}")
                    except Exception as metadata_error:
                        logger.error(f"Error updating metadata after vector deletion: {str(metadata_error)}")
                        # Continue anyway since vectors are already deleted from the index
                else:
                    logger.warning(f"Metadata file not found: {self.metadata_file}")
                return True
            else:
                return True  # Return true if there were no vectors to delete
        except Exception as e:
            logger.error(f"Error deleting existing vectors for file {file_id}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _update_mapping(self, file_id: str, vector_ids: List[str]) -> bool:
        """Update the file metadata with vector IDs.
        
        Args:
            file_id: ID of the file.
            vector_ids: List of vector IDs.
            
        Returns:
            True if metadata was updated successfully, False otherwise.
        """
        try:
            import json
        
            # Update the file metadata to include vector IDs
            
            if self.metadata_file.exists():
                # Load file metadata
                with open(self.metadata_file, "r") as f:
                    metadata = json.load(f)
                
                # Find and update the file entry
                file_updated = False
                for file_entry in metadata:
                    if file_entry.get("id") == file_id:
                        # Use related_vectors field instead of vector_ids
                        file_entry["related_vectors"] = vector_ids
                        file_entry["processing_status"] = "complete"  # Update status to complete
                        file_updated = True
                        break
                
                if file_updated:
                    # Save updated metadata
                    with open(self.metadata_file, "w") as f:
                        json.dump(metadata, f, indent=2)
                else:
                    logger.warning(f"[VECTOR DEBUG] File not found in metadata: {file_id}")
            else:
                logger.warning(f"[VECTOR DEBUG] Metadata file not found: {self.metadata_file}")
            
            return True
        except Exception as e:
            logger.error(f"[VECTOR DEBUG] Error updating file metadata with vector IDs for file {file_id}: {str(e)}")
            import traceback
            logger.error(f"[VECTOR DEBUG] Traceback: {traceback.format_exc()}")
            return False
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar content.
        
        Args:
            query: Query string.
            limit: Maximum number of results to return.
            
        Returns:
            List of search results with metadata.
        """
        try:
            # Generate embedding for query
            query_embedding = get_embedding(query)
            query_vector = np.array([query_embedding], dtype=np.float32)
            
            # Search for similar vectors
            results = search_vectors_in_index(
                self.index,
                query_vector,
                str(self.vectors_dir),
                k=limit
            )
            
            # Sort results by similarity (already done by FAISS)
            # Then by recency (upload_date)
            results.sort(
                key=lambda x: (
                    x.get("distance", 1.0),  # Primary sort by distance (similarity)
                    -1 * (datetime.fromisoformat(x.get("upload_date", "1970-01-01T00:00:00")).timestamp() 
                         if x.get("upload_date") else 0)  # Secondary sort by recency
                )
            )
            
            return results
        except Exception as e:
            logger.error(f"Error searching vectors: {str(e)}")
            return []
