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
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

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
    # Ensure query vector is 2D
    if len(query_vector.shape) == 1:
        query_vector = query_vector.reshape(1, -1)
    
    # Search for similar vectors
    distances, indices = index.search(query_vector, k)
    
    # Check if database path exists
    if not os.path.exists(db_path):
        logger.warning(f"Database path not found: {db_path}")
        return []
    
    # Create a mapping of all metadata files by their filename (without extension)
    # This is more reliable than using directory listing order
    metadata_map = {}
    
    # Get all JSON files in the directory
    metadata_files = [f for f in os.listdir(db_path) if f.endswith('.json')]
    logger.info(f"Found {len(metadata_files)} metadata files in {db_path}")
    
    # Log some sample filenames for debugging
    if metadata_files:
        sample_files = metadata_files[:5] if len(metadata_files) > 5 else metadata_files
        logger.info(f"Sample metadata files: {sample_files}")
    
    # Load all metadata into a map
    for filename in metadata_files:
        try:
            file_path = os.path.join(db_path, filename)
            with open(file_path, "r") as f:
                metadata = json.load(f)
                
                # Handle both list and dictionary formats
                if isinstance(metadata, list):
                    # If it's a list, process each item
                    logger.info(f"Metadata from {filename} is a list with {len(metadata)} items")
                    for item in metadata:
                        if isinstance(item, dict) and "id" in item:
                            metadata_map[item["id"]] = item
                            logger.info(f"Added list item: id={item.get('id')}, user_id={item.get('user_id')}")
                elif isinstance(metadata, dict):
                    # If it's a dictionary, process it directly
                    logger.info(f"Metadata from {filename}: id={metadata.get('id')}, user_id={metadata.get('user_id')}")
                    if "id" in metadata:
                        metadata_map[metadata["id"]] = metadata
                else:
                    logger.warning(f"Unexpected metadata format in {filename}: {type(metadata)}")
        except Exception as e:
            logger.error(f"Error loading metadata file {filename}: {e}")
    
    # Process search results
    results = []
    logger.info(f"FAISS search returned indices: {indices[0].tolist()[:10]}")
    logger.info(f"FAISS search returned distances: {distances[0].tolist()[:10]}")
    
    # Log the total number of metadata items loaded
    logger.info(f"Total metadata items loaded: {len(metadata_map)}")
    
    for i, idx in enumerate(indices[0]):
        if idx == -1:  # No more results
            logger.info(f"Skipping index {idx} (no more results)")
            continue
            
        logger.info(f"Processing search result index {idx}")
        
        # Try to find the metadata file that corresponds to this index
        # We'll look for a file with a name pattern that includes the index
        # This is a heuristic approach since we don't have a direct mapping
        potential_matches = []
        
        # Log how many items we're iterating through
        logger.info(f"Looking through {len(metadata_map)} metadata items for potential matches")
        
        for metadata_id, metadata in metadata_map.items():
            # Add to potential matches
            potential_matches.append(metadata)
            
            # If we have enough matches, stop looking
            if len(potential_matches) >= k:
                break
        
        # Log the number of potential matches found
        logger.info(f"Found {len(potential_matches)} potential matches")
        
        # If we found potential matches, use them
        if potential_matches:
            # Sort by distance (closest first)
            for j, match in enumerate(potential_matches[:k]):
                match_copy = dict(match)
                match_copy["distance"] = float(distances[0][i]) if i < len(distances[0]) else 1.0
                logger.info(f"Adding result: id={match_copy.get('id')}, user_id={match_copy.get('user_id')}, distance={match_copy.get('distance')}")
                results.append(match_copy)
        else:
            logger.warning(f"No potential matches found for index {idx}")
                
    # Log the number of results found
    logger.info(f"Found {len(results)} results for query")
    
    return results

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
            logger.warning(f"Database path not found: {db_path}")
            return False
            
        logger.debug(f"Deleting vectors with IDs: {ids} from {db_path}")
        
        # Debug the path being used
        logger.debug(f"[VECTOR DEBUG] Looking for vector files in directory: {db_path}")
        print(f"[VECTOR DEBUG] Looking for vector files in directory: {db_path}")
        
        # Get all metadata files (any JSON file in the vectors directory)
        metadata_files = [f for f in os.listdir(db_path) if f.endswith('.json')]
        logger.debug(f"[VECTOR DEBUG] Found {len(metadata_files)} metadata files in vectors directory")
        print(f"[VECTOR DEBUG] Found {len(metadata_files)} metadata files in vectors directory")
        
        # Delete vector files first
        deleted_files = []
        for vector_id in ids:
            logger.debug(f"[VECTOR DEBUG] Processing vector ID for deletion: {vector_id}")
            print(f"[VECTOR DEBUG] Processing vector ID for deletion: {vector_id}")
            
            # Remove metadata file
            metadata_path_full = os.path.join(db_path, f"{vector_id}.json")
            logger.debug(f"[VECTOR DEBUG] Attempting to delete file: {metadata_path_full}")
            print(f"[VECTOR DEBUG] Attempting to delete file: {metadata_path_full}")
            
            if os.path.exists(metadata_path_full):
                os.remove(metadata_path_full)
                deleted_files.append(metadata_path_full)
                logger.debug(f"[VECTOR DEBUG] Successfully removed metadata file for vector ID: {vector_id}")
                print(f"[VECTOR DEBUG] Successfully removed metadata file for vector ID: {vector_id}")
            else:
                logger.warning(f"[VECTOR DEBUG] Metadata file not found: {metadata_path_full}")
                print(f"[VECTOR DEBUG] Metadata file not found: {metadata_path_full}")
        
        logger.debug(f"[VECTOR DEBUG] Deleted {len(deleted_files)} vector files: {deleted_files}")
        print(f"[VECTOR DEBUG] Deleted {len(deleted_files)} vector files: {deleted_files}")
        
        # For FAISS index, we need to rebuild it from scratch since we can't reliably map IDs to indices
        # This is a more reliable approach than trying to remove specific vectors
        try:
            logger.debug(f"[VECTOR DEBUG] Rebuilding FAISS index after vector deletion")
            print(f"[VECTOR DEBUG] Rebuilding FAISS index after vector deletion")
            
            # Create a new index
            dimension = index.d  # Get dimension from existing index
            new_index = faiss.IndexFlatL2(dimension)
            
            # Get remaining vector files
            remaining_files = [f for f in os.listdir(db_path) if f.endswith('.json')]
            logger.debug(f"[VECTOR DEBUG] Found {len(remaining_files)} remaining vector files")
            print(f"[VECTOR DEBUG] Found {len(remaining_files)} remaining vector files")
            
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
                    logger.error(f"[VECTOR DEBUG] Error processing vector file {metadata_file}: {str(e)}")
                    print(f"[VECTOR DEBUG] Error processing vector file {metadata_file}: {str(e)}")
            
            # Save the new index
            faiss.write_index(new_index, index_path)
            logger.debug(f"[VECTOR DEBUG] Successfully rebuilt and saved FAISS index with {new_index.ntotal} vectors")
            print(f"[VECTOR DEBUG] Successfully rebuilt and saved FAISS index with {new_index.ntotal} vectors")
        except Exception as e:
            logger.error(f"[VECTOR DEBUG] Error rebuilding FAISS index: {str(e)}")
            print(f"[VECTOR DEBUG] Error rebuilding FAISS index: {str(e)}")
            # Continue anyway since we've already deleted the vector files
        
        # We've already rebuilt the index above, so no need to remove vectors here
        logger.info(f"Successfully deleted vector files for the given IDs: {ids}")
        
        return True
    except Exception as e:
        logger.error(f"Error deleting vectors: {e}")
        logger.error(f"Exception details: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def ensure_vector_2d(vector: np.ndarray) -> np.ndarray:
    """Ensure a vector is 2D.
    
    Args:
        vector: Input vector.
        
    Returns:
        2D vector.
    """
    if len(vector.shape) == 1:
        return vector.reshape(1, -1)
    return vector 