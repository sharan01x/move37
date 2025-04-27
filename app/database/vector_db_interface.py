#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Vector database interface for the Move 37 application.
This class provides a standardized interface for vector database operations
across different components of the application.
"""


# PLEASE BE REMINDED THAT THIS IS THE INTERFACE CLASS THAT IS USED BY OTHER APPLICATION SPECIFIC DATABASE INTERFACES.
# DO NOT MAKE EDITS HERE UNLESS YOU WANT THE CHANGES PROPOGATED TO ALL CHILD DB INTERFACES.

import os
import numpy as np
import uuid
import logging
from typing import List, Dict, Any, Optional

from app.core.config import EMBEDDING_MODEL_DIMENSIONS
from app.utils.vector_utils import (
    init_faiss_index,
    add_vectors_to_index,
    search_vectors_in_index,
    delete_vectors_from_index,
    ensure_vector_2d
)

logger = logging.getLogger(__name__)

class VectorDBInterface:
    """
    Interface for vector database operations.
    Provides a standardized interface for managing vectors and their metadata
    across different components of the application.
    """

    def __init__(self, db_path: str, user_id: str, dimension: int = EMBEDDING_MODEL_DIMENSIONS):
        """
        Initialize the vector database interface.
        
        Args:
            db_path: Base path to the vector database (from config).
            user_id: ID of the user whose data is being managed.
                    A user-specific subdirectory will be created.
            dimension: Dimension of the vectors.
        """
        self.base_db_path = db_path
        self.user_id = user_id
        self.dimension = dimension
        
        # Create the final db_path based on whether user_id is provided
        if user_id:
            self.db_path = os.path.join(self.base_db_path, user_id)
        else:
            self.db_path = self.base_db_path
            
        # Create necessary directories
        os.makedirs(self.db_path, exist_ok=True)
        
        # Initialize FAISS index
        self.index_path = os.path.join(self.db_path, "faiss_index")
        self.index = init_faiss_index(dimension, self.index_path)
        
        logger.info(f"Initialized VectorDBInterface at path: {self.db_path}")
    
    def _resolve_user_id(self, user_id: Optional[str] = None) -> str:
        """
        Helper method to resolve the user ID for database operations.
        
        This standardizes user ID handling across all methods and derived classes,
        enforcing the application's user-ID-based architecture.
        
        Args:
            user_id: Optional user ID to override the instance user_id.
                    If provided, this takes precedence over self.user_id.
        
        Returns:
            The resolved user ID (either from parameter or instance).
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        resolved_id = user_id if user_id is not None else self.user_id
        if not resolved_id:
            raise ValueError("User ID is required for this operation. Please provide a user ID.")
        return resolved_id
    
    def add_vectors(self, vectors: np.ndarray, metadata: List[Dict[str, Any]], user_id: Optional[str] = None) -> List[str]:
        """
        Add vectors to the database.
        
        Args:
            vectors: Vectors to add.
            metadata: Metadata for the vectors.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            List of IDs for the added vectors.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        # Ensure vectors are 2D
        vectors = ensure_vector_2d(vectors)
        
        # Add IDs to metadata if not present
        # Resolve the user ID
        resolved_user_id = self._resolve_user_id(user_id)
        
        for meta in metadata:
            if "id" not in meta:
                meta["id"] = str(uuid.uuid4())
            
            # Add user_id to metadata if it was provided
            if resolved_user_id and "user_id" not in meta:
                meta["user_id"] = resolved_user_id
        
        return add_vectors_to_index(
            self.index,
            vectors,
            metadata,
            self.db_path,  # Use db_path directly instead of a forced metadata subfolder
            self.index_path
        )
    
    def search_vectors(self, query_vector: np.ndarray, k: int = 5, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for vectors by query vector.
        
        Args:
            query_vector: Query vector.
            k: Number of results to return.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            List of metadata for the k most similar vectors.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        return search_vectors_in_index(
            self.index,
            query_vector,
            self.db_path,  # Use db_path directly instead of a forced metadata subfolder
            k
        )
    
    def delete_vectors(self, ids: List[str], user_id: Optional[str] = None) -> bool:
        """
        Delete vectors from the database.
        
        Args:
            ids: List of IDs to delete.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            True if successful, False otherwise.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        return delete_vectors_from_index(
            self.index,
            ids,
            self.db_path,  # Use db_path directly instead of a forced metadata subfolder
            self.index_path
        )
        
    def semantic_search(self, query: str, embedding_function, top_k: int = 5, 
                        filter_by_user: bool = True, min_score: float = 0.0,
                        user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform semantic search using the provided query and embedding function.
        
        This is a generalized method that can be used by child classes to perform
        semantic search with user-specific filtering and improved relevance scoring.
        
        Args:
            query: The search query string.
            embedding_function: Function to convert query to vector embedding.
            top_k: Number of results to return.
            filter_by_user: Whether to filter results by user_id.
            min_score: Minimum similarity score (0-1) for results to be included.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            List of results with metadata and similarity scores.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        try:
            # Generate embedding for the query
            query_embedding = embedding_function(query)
            
            # Search for similar vectors
            results = self.search_vectors(query_embedding, k=top_k * 2)  # Get more results for filtering
            
            # Filter results if needed
            filtered_results = []
            # Resolve the user ID for filtering
            resolved_user_id = self._resolve_user_id(user_id)
            
            for result in results:
                # Skip if we're filtering by user and the user_id doesn't match
                if filter_by_user and resolved_user_id and result.get("user_id") != resolved_user_id:
                    continue
                    
                # Add similarity score (convert from distance)
                if "distance" in result:
                    # Convert distance to similarity score (0-1 range)
                    result["similarity"] = 1.0 - min(result["distance"], 1.0)
                    
                    # Skip if below minimum score
                    if result["similarity"] < min_score:
                        continue
                
                filtered_results.append(result)
                
                # Stop once we have enough results
                if len(filtered_results) >= top_k:
                    break
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error in semantic_search: {e}")
            return []
