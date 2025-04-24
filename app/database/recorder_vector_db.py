#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Recorder Vector Database Interface for managing recorder embeddings.
"""

import os
from typing import List, Dict, Any, Optional, Union
import numpy as np
from datetime import datetime

from app.core.config import USER_DATA_DIR, EMBEDDING_MODEL_DIMENSIONS
from app.database.vector_db_interface import VectorDBInterface

class RecorderVectorDBInterface(VectorDBInterface):
    """Interface for recorder vector database operations."""
    
    def __init__(self, user_id: str, dimension: int = EMBEDDING_MODEL_DIMENSIONS):
        """
        Initialize the recorder vector database interface.
        
        Args:
            user_id: The ID of the user whose data is being managed.
            dimension: Dimension of the vectors. Default is from config.EMBEDDING_MODEL_DIMENSIONS.
        """
        if not user_id:
            raise ValueError("user_id must be provided")
        
        # Initialize the base class with the user data directory path
        super().__init__(db_path=USER_DATA_DIR, user_id=user_id, dimension=dimension)
        
        print(f"[RecorderVectorDB] Initialized with path: {self.db_path}")
    
    def add_recording(self, text: str, embedding: np.ndarray, metadata: Dict[str, Any]) -> str:
        """
        Add a recording to the database.
        
        Args:
            text: The recorded text.
            embedding: Vector embedding of the text.
            metadata: Additional metadata for the recording.
            
        Returns:
            ID of the added recording.
        """
        # Ensure the embedding is 2D
        if len(embedding.shape) == 1:
            embedding = embedding.reshape(1, -1)
        
        # Add timestamp to metadata (user_id is already added by VectorDBInterface)
        metadata['timestamp'] = datetime.now().isoformat()
        
        # Add the embedding to the index
        ids = self.add_vectors(embedding, [metadata])
        return ids[0]
    
    def search_recordings(self, query: str, query_embedding: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for recordings by query.
        
        Args:
            query: Query string.
            query_embedding: Vector embedding of the query.
            k: Number of results to return.
            
        Returns:
            List of metadata for the k most similar recordings.
        """
        # Get results from vector search
        results = self.search_vectors(query_embedding, k)
        
        # Add the query to the results
        for result in results:
            result['query'] = query
        
        return results 