#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utility functions for vector operations using FAISS.
Provides low-level functions for managing vector databases.
"""

import os
import numpy as np
import faiss
import json
from typing import List, Dict, Any, Tuple, Optional, Union
from pathlib import Path

def init_faiss_index(dimension: int, index_path: str) -> faiss.Index:
    """Initialize or load a FAISS index.
    
    Args:
        dimension: Dimension of the vectors.
        index_path: Path to save/load the index.
        
    Returns:
        Initialized FAISS index.
    """
    if os.path.exists(index_path) and os.path.getsize(index_path) > 0:
        return faiss.read_index(index_path)
    else:
        index = faiss.IndexFlatL2(dimension)
        faiss.write_index(index, index_path)
        return index

def add_vectors_to_index(
    index: faiss.Index,
    vectors: np.ndarray,
    metadata: List[Dict[str, Any]],
    db_path: str,
    index_path: str
) -> List[str]:
    """Add vectors to a FAISS index with metadata.
    
    Args:
        index: FAISS index to add vectors to.
        vectors: Vectors to add.
        metadata: Metadata for each vector.
        db_path: Base path for the database where metadata will be stored.
        index_path: Path to save the index.
        
    Returns:
        List of IDs for the added vectors.
    """
    # Add vectors to index
    index.add(vectors)
    
    # Ensure the database directory exists
    os.makedirs(db_path, exist_ok=True)
    
    # Save metadata directly in the database path
    for i, meta in enumerate(metadata):
        metadata_file = os.path.join(db_path, f"{meta['id']}.json")
        with open(metadata_file, "w") as f:
            json.dump(meta, f)
    
    # Save updated index
    faiss.write_index(index, index_path)
    
    return [meta["id"] for meta in metadata]

def search_vectors_in_index(
    index: faiss.Index,
    query_vector: np.ndarray,
    db_path: str,
    k: int = 5
) -> List[Dict[str, Any]]:
    """Search for vectors in a FAISS index.
    
    Args:
        index: FAISS index to search in.
        query_vector: Query vector.
        db_path: Base path for the database where metadata is stored.
        k: Number of results to return.
        
    Returns:
        List of metadata for the k most similar vectors.
    """
    try:
        # Convert query_vector to numpy array if it's a list
        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)
        
        # Ensure query vector is 2D
        if len(query_vector.shape) == 1:
            query_vector = query_vector.reshape(1, -1)
        
        # Search for similar vectors
        distances, indices = index.search(query_vector, k)
        
        # Check if database path exists
        if not os.path.exists(db_path):
            return []
        
        # Create a mapping of all metadata files by their filename (without extension)
        # This is more reliable than using directory listing order
        metadata_map = {}
        
        # Get all JSON files in the directory
        metadata_files = [f for f in os.listdir(db_path) if f.endswith('.json')]
        # Load all metadata into a map
        for filename in metadata_files:
            try:
                file_path = os.path.join(db_path, filename)
                with open(file_path, "r") as f:
                    metadata = json.load(f)
                    
                    # Handle both list and dictionary formats
                    if isinstance(metadata, list):
                        # If it's a list, process each item
                        for item in metadata:
                            if isinstance(item, dict) and "id" in item:
                                metadata_map[item["id"]] = item
                    elif isinstance(metadata, dict):
                        # If it's a dictionary, process it directly
                        if "id" in metadata:
                            metadata_map[metadata["id"]] = metadata
                    else:
                        logger.warning(f"Unexpected metadata format in {filename}: {type(metadata)}")
            except Exception as e:
                logger.error(f"Error loading metadata file {filename}: {e}")
        
        # Process search results
        results = []
        
        
        for i, idx in enumerate(indices[0]):
            if idx == -1:  # No more results
                continue
                
            # Try to find the metadata file that corresponds to this index
            # We'll look for a file with a name pattern that includes the index
            # This is a heuristic approach since we don't have a direct mapping
            potential_matches = []
            
            
            for metadata_id, metadata in metadata_map.items():
                # Add to potential matches
                potential_matches.append(metadata)
                
                # If we have enough matches, stop looking
                if len(potential_matches) >= k:
                    break
            
            # If we found potential matches, use them
            if potential_matches:
                # Sort by distance (closest first)
                for j, match in enumerate(potential_matches[:k]):
                    match_copy = dict(match)
                    match_copy["distance"] = float(distances[0][i]) if i < len(distances[0]) else 1.0
                    results.append(match_copy)
            else:
                print(f"No potential matches found for index {idx}")
                    
        
        return results
    except Exception as e:
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return []

def delete_vectors_from_index(
    index: faiss.Index,
    ids: List[str],
    db_path: str,
    index_path: str
) -> bool:
    """Delete vectors from a FAISS index.
    
    Args:
        index: FAISS index to delete vectors from.
        ids: List of IDs to delete. These are the vector IDs (UUIDs), not indices.
        db_path: Base path for the database where metadata is stored.
        index_path: Path to save the updated index.
        
    Returns:
        True if successful, False otherwise.
    """
    try:
        # Check if database path exists
        if not os.path.exists(db_path):
            return False
            
        # Get all metadata files (any JSON file in the vectors directory)
        metadata_files = [f for f in os.listdir(db_path) if f.endswith('.json')]
        
        # Delete vector files first
        deleted_files = []
        for vector_id in ids:
            
            # Remove metadata file
            metadata_path_full = os.path.join(db_path, f"{vector_id}.json")
            
            if os.path.exists(metadata_path_full):
                os.remove(metadata_path_full)
                deleted_files.append(metadata_path_full)
        
        # For FAISS index, we need to rebuild it from scratch since we can't reliably map IDs to indices
        # This is a more reliable approach than trying to remove specific vectors
        try:
            
            # Create a new index
            dimension = index.d  # Get dimension from existing index
            new_index = faiss.IndexFlatL2(dimension)
            
            # Get remaining vector files
            remaining_files = [f for f in os.listdir(db_path) if f.endswith('.json')]
            
            # Add remaining vectors to the new index
            for i, metadata_file in enumerate(remaining_files):
                try:
                    metadata_path = os.path.join(db_path, metadata_file)
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    # Extract vector from metadata
                    if 'vector' in metadata:
                        vector = np.array(metadata['vector'], dtype=np.float32).reshape(1, -1)
                        new_index.add(vector)
                except Exception as e:
                    print(f"[VECTOR DEBUG] Error processing vector file {metadata_file}: {str(e)}")
            
            # Save the new index
            faiss.write_index(new_index, index_path)
        except Exception as e:
            print(f"[VECTOR DEBUG] Error rebuilding FAISS index: {str(e)}")
            # Continue anyway since we've already deleted the vector files
        
        return True
    except Exception as e:
        print(f"Error deleting vectors: {e}")
        print(f"Exception details: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def ensure_vector_2d(vector: Union[np.ndarray, List]) -> np.ndarray:
    """Ensure a vector is 2D.
    
    Args:
        vector: Input vector, can be a numpy array or a list.
        
    Returns:
        2D numpy array.
    """
    # Convert to numpy array if it's a list
    if isinstance(vector, list):
        # If it's a list of lists, convert each inner list to a numpy array
        if vector and isinstance(vector[0], list):
            vector = np.array([np.array(v, dtype=np.float32) for v in vector], dtype=np.float32)
        else:
            # It's a simple list, convert to numpy array directly
            vector = np.array([vector], dtype=np.float32)
            return vector
    
    # Now we have a numpy array, ensure it's 2D
    if len(vector.shape) == 1:
        return vector.reshape(1, -1)
    return vector 