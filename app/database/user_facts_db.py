#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
User Facts Database Interface for storing and retrieving user facts.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

import numpy as np
from pathlib import Path

from app.core.config import USER_FACTS_DB_PATH, EMBEDDING_MODEL_DIMENSIONS
from app.utils.embeddings import get_embedding
from app.database.vector_db_interface import VectorDBInterface

logger = logging.getLogger(__name__)

class UserFactsDBInterface:
    """Interface for storing and retrieving user facts."""

    def __init__(self, user_id: str, db_path: str = USER_FACTS_DB_PATH):
        """Initialize the UserFactsDBInterface.
        
        Args:
            user_id: ID of the user whose facts are being managed.
                    A user-specific subdirectory will be created.
            db_path: Path to the user facts database.
        """
        self.user_id = user_id
        self.db_path = db_path
        
        # Create the user-specific db_path
        self.user_db_path = os.path.join(self.db_path, user_id)
            
        os.makedirs(self.user_db_path, exist_ok=True)
        
        # Initialize the vector database for semantic search
        # Use the same path as the user facts database to avoid creating additional subfolders
        self.vector_db = VectorDBInterface(
            db_path=USER_FACTS_DB_PATH,  # Use the base path directly from config
            user_id=user_id
        )
        
        # Path to the JSON file storing all user facts
        self.facts_file = os.path.join(self.user_db_path, "user_facts.json")
        
        # Initialize the facts file if it doesn't exist
        if not os.path.exists(self.facts_file):
            with open(self.facts_file, "w") as f:
                json.dump([], f)
        
        # Counter for operations (add, update, delete) to trigger periodic rebuilds
        self.operations_counter = 0
        self.rebuild_threshold = 10  # Rebuild after every 10 operations
        
        logger.info(f"Initialized UserFactsDBInterface at path: {self.user_db_path}")
    
    def add_fact(self, fact: str, category: str, source_text: str, confidence: float = 1.0) -> str:
        """Add a new user fact to the database.
        
        Args:
            fact: The user fact to store.
            category: Category of the fact (e.g., "preference", "personal_info").
            source_text: The original text from which the fact was extracted.
            confidence: Confidence score for the fact (0.0 to 1.0).
            
        Returns:
            fact_id: The ID of the newly added fact or the ID of an existing similar fact.
        """
        # First, search for semantically similar facts
        similar_facts = self.search_facts(fact, top_k=5)
        
        # Check if any existing fact is semantically equivalent
        for existing_fact in similar_facts:
            # If we find a very similar fact with high confidence
            if existing_fact["category"] == category:
                # Get embeddings for both facts
                try:
                    new_embedding = get_embedding(fact)
                    existing_embedding = get_embedding(existing_fact["fact"])
                    
                    # Calculate cosine similarity
                    similarity = np.dot(new_embedding, existing_embedding) / (
                        np.linalg.norm(new_embedding) * np.linalg.norm(existing_embedding)
                    )
                    
                    # If the facts are very similar (similarity > 0.95)
                    if similarity > 0.95:
                        # If the new fact has higher confidence, update the existing one
                        if confidence > existing_fact["confidence"]:
                            self.update_fact(existing_fact["id"], {
                                "confidence": confidence,
                                "source_text": source_text,
                                "updated_at": datetime.now().isoformat()
                            })
                        return existing_fact["id"]
                except Exception as e:
                    logger.error(f"Error comparing fact embeddings: {e}")
                    # Continue with adding the new fact if comparison fails
        
        # If no similar fact found, proceed with adding the new fact
        # Generate a unique ID for the fact
        fact_id = str(uuid.uuid4())
        
        # Get the embedding for the fact
        try:
            embedding = get_embedding(fact)
        except Exception as e:
            logger.error(f"Error getting embedding for fact: {e}")
            embedding = np.zeros(EMBEDDING_MODEL_DIMENSIONS).tolist()
        
        # Create the fact object
        fact_obj = {
            "id": fact_id,
            "fact": fact,
            "category": category,
            "source_text": source_text,
            "confidence": confidence,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Add the fact to the JSON file
        facts = self._load_facts()
        facts.append(fact_obj)
        self._save_facts(facts)
        
        # Add the fact to the vector database
        try:
            # Convert embedding to numpy array if it's a list
            if isinstance(embedding, list):
                embedding = np.array(embedding, dtype=np.float32)
            
            # Ensure the embedding is 2D
            if len(embedding.shape) == 1:
                embedding = embedding.reshape(1, -1)
            
            self.vector_db.add_vectors(
                vectors=embedding,
                metadata=[fact_obj]
            )
        except Exception as e:
            logger.error(f"Error adding fact to vector database: {e}")
        
        # Increment operations counter and check if rebuild is needed
        self.operations_counter += 1
        if self.operations_counter >= self.rebuild_threshold:
            logger.info(f"Operation threshold reached ({self.operations_counter}). Triggering vector database rebuild.")
            self.rebuild_vector_db()
            self.operations_counter = 0
        
        return fact_id
    
    def get_fact(self, fact_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a user fact by ID.
        
        Args:
            fact_id: The ID of the fact to retrieve.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            The fact object if found, None otherwise.
        """
        # Resolve the user ID
        resolved_user_id = user_id if user_id is not None else self.user_id
        if not resolved_user_id:
            logger.error("User ID is required for retrieving facts. No user ID provided.")
            return None
            
        # If user_id is different from self.user_id, we need to create a temporary path
        facts_file_path = self.facts_file
        if user_id and user_id != self.user_id:
            temp_path = os.path.join(self.db_path, user_id)
            facts_file_path = os.path.join(temp_path, "user_facts.json")
            if not os.path.exists(facts_file_path):
                logger.error(f"Facts file for user {user_id} not found at {facts_file_path}")
                return None
        
        # Load facts from the correct user file
        try:
            with open(facts_file_path, "r") as f:
                facts = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading facts for retrieval: {e}")
            return None
        
        # Find the fact by ID
        for fact in facts:
            if fact["id"] == fact_id:
                return fact
                
        logger.warning(f"Fact with ID {fact_id} not found for user {resolved_user_id}")
        return None
    
    def get_all_facts(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all user facts.
        
        Args:
            user_id: Optional user ID to override the instance user_id.
        
        Returns:
            A list of all fact objects.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        # Resolve the user ID
        resolved_user_id = user_id if user_id is not None else self.user_id
        if not resolved_user_id:
            raise ValueError("User ID is required for this operation. Please provide a user ID.")
            
        # If user_id is different from self.user_id, we need to create a temporary path
        if user_id and user_id != self.user_id:
            temp_path = os.path.join(self.db_path, user_id)
            facts_file = os.path.join(temp_path, "user_facts.json")
            if os.path.exists(facts_file):
                with open(facts_file, "r") as f:
                    return json.load(f)
            return []
        
        return self._load_facts()
    
    def get_facts_by_category(self, category: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all user facts in a specific category.
        
        Args:
            category: The category to filter by.
            user_id: Optional user ID to override the instance user_id.
            
        Returns:
            A list of fact objects in the specified category.
            
        Raises:
            ValueError: If no user ID is available (neither passed nor set in instance).
        """
        # Get all facts for the specified user
        all_facts = self.get_all_facts(user_id=user_id)
        
        # Filter by category
        return [fact for fact in all_facts if fact["category"] == category]
    
    def search_facts(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for user facts semantically similar to the query.
        
        Args:
            query: The search query.
            top_k: The number of results to return.
            
        Returns:
            A list of fact objects semantically similar to the query.
        """
        try:
            logger.info(f"Searching for facts with query: '{query}', user_id: '{self.user_id}', top_k: {top_k}")
            
            # Use our custom semantic search implementation
            return self.semantic_search(query, top_k)
        except Exception as e:
            logger.error(f"Error in search_facts: {e}")
            return []
    
    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Perform semantic search for user facts.
        
        This method can use two different implementations:
        1. Direct file-based search (current implementation)
        2. Vector database search (via base class)
        
        The direct file-based search is used by default as it has proven more reliable
        for user facts, but the code can be easily switched to use the vector database
        implementation if needed.
        
        Args:
            query: The search query.
            top_k: The number of results to return.
            
        Returns:
            A list of fact objects semantically similar to the query.
        """
        # Use the direct file-based implementation by default
        return self._direct_semantic_search(query, top_k)
        
        # Alternatively, use the vector database implementation from the base class
        # return self._vector_db_semantic_search(query, top_k)
    
    def _vector_db_semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Vector database implementation of semantic search using the base class method.
        
        Args:
            query: The search query.
            top_k: The number of results to return.
            
        Returns:
            A list of fact objects semantically similar to the query.
        """
        try:
            logger.info(f"Using vector DB semantic search with query: '{query}', user_id: '{self.user_id}'")
            
            # Use the base class implementation
            results = self.vector_db.semantic_search(
                query=query,
                embedding_function=get_embedding,
                top_k=top_k,
                filter_by_user=True,
                min_score=0.0
            )
            
            # Log the results for debugging
            logger.info(f"Vector DB semantic search returned {len(results)} results")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in _vector_db_semantic_search: {e}")
            return []
    
    def _direct_semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Direct file-based implementation of semantic search.
        
        This method computes embeddings for the query and all facts, then finds the most
        similar facts based on cosine similarity.
        
        Args:
            query: The search query.
            top_k: The number of results to return.
            
        Returns:
            A list of fact objects semantically similar to the query.
        """
        try:
            # Get all facts for this user
            all_facts = self._load_facts()
            logger.info(f"Loaded {len(all_facts)} facts from JSON file for semantic search")
            
            if not all_facts:
                logger.warning("No facts found for this user")
                return []
            
            # Get the embedding for the query
            query_embedding = get_embedding(query)
            
            # Convert to numpy array if needed
            if isinstance(query_embedding, list):
                query_embedding = np.array(query_embedding, dtype=np.float32)
            
            # Normalize the query embedding
            query_embedding_norm = query_embedding / np.linalg.norm(query_embedding)
            
            # Prepare to store similarities
            fact_similarities = []
            
            # Calculate similarity for each fact
            for fact in all_facts:
                try:
                    # Get or compute the fact embedding
                    fact_embedding = get_embedding(fact["fact"])
                    
                    # Convert to numpy array if needed
                    if isinstance(fact_embedding, list):
                        fact_embedding = np.array(fact_embedding, dtype=np.float32)
                    
                    # Normalize the fact embedding
                    fact_embedding_norm = fact_embedding / np.linalg.norm(fact_embedding)
                    
                    # Calculate cosine similarity
                    similarity = np.dot(query_embedding_norm, fact_embedding_norm)
                    
                    # Store the fact and its similarity
                    fact_similarities.append((fact, similarity))
                    
                except Exception as e:
                    logger.error(f"Error calculating similarity for fact {fact.get('id')}: {e}")
            
            # Sort by similarity (highest first)
            fact_similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Log the top similarities for debugging
            for i, (fact, similarity) in enumerate(fact_similarities[:3]):
                logger.info(f"Top similarity {i}: id={fact.get('id')}, similarity={similarity:.4f}, fact='{fact.get('fact')}'")
            
            # Return the top_k most similar facts
            return [fact for fact, similarity in fact_similarities[:top_k]]
            
        except Exception as e:
            logger.error(f"Error in _direct_semantic_search: {e}")
            return []
    
    def update_fact(self, fact_id: str, updates: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        """Update a user fact.
        
        Args:
            fact_id: The ID of the fact to update.
            updates: A dictionary of fields to update.
            user_id: Optional user ID to override the instance user_id. 
        Returns:
            True if the fact was updated, False otherwise.
        """
        # Resolve the user ID
        resolved_user_id = user_id if user_id is not None else self.user_id
        if not resolved_user_id:
            logger.error("User ID is required for updating facts. No user ID provided.")
            return False
            
        # If user_id is different from self.user_id, we need to create a temporary path
        facts_file_path = self.facts_file
        if user_id and user_id != self.user_id:
            temp_path = os.path.join(self.db_path, user_id)
            facts_file_path = os.path.join(temp_path, "user_facts.json")
            if not os.path.exists(facts_file_path):
                logger.error(f"Facts file for user {user_id} not found at {facts_file_path}")
                return False
        
        # Load facts from the correct user file
        try:
            with open(facts_file_path, "r") as f:
                facts = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading facts for update: {e}")
            return False
        
        # Find the fact to update
        updated = False
        for i, fact in enumerate(facts):
            if fact["id"] == fact_id:
                # Update the fact
                for key, value in updates.items():
                    if key in fact and key not in ["id", "created_at"]:
                        fact[key] = value
                
                # Update the updated_at timestamp
                fact["updated_at"] = datetime.now().isoformat()
                updated = True
                break
        
        if not updated:
            logger.warning(f"Fact with ID {fact_id} not found for user {resolved_user_id}")
            return False
        
        # Save the updated facts back to the correct file
        try:
            with open(facts_file_path, "w") as f:
                json.dump(facts, f, indent=2)
            
            # Update the fact in the vector database if the text changed
            if "fact" in updates:
                try:
                    # Get the new embedding
                    embedding = get_embedding(updates["fact"])
                    
                    # Convert embedding to numpy array if it's a list
                    if isinstance(embedding, list):
                        embedding = np.array(embedding, dtype=np.float32)
                    
                    # Ensure the embedding is 2D
                    if len(embedding.shape) == 1:
                        embedding = embedding.reshape(1, -1)
                    
                    # We can't directly update in FAISS, so we'll need to delete and re-add
                    # This is a simplification and might not work perfectly with FAISS
                    # For a production system, consider using a database that supports updates
                    # or implement a more sophisticated update mechanism
                except Exception as e:
                    logger.error(f"Error updating fact in vector database: {e}")
            
            # Increment operations counter and check if rebuild is needed
            self.operations_counter += 1
            if self.operations_counter >= self.rebuild_threshold:
                logger.info(f"Operation threshold reached ({self.operations_counter}). Triggering vector database rebuild.")
                self.rebuild_vector_db()
                self.operations_counter = 0
            
            logger.info(f"Successfully updated fact {fact_id} for user {resolved_user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving facts after update: {e}")
            return False
    
    def delete_fact(self, fact_id: str, user_id: Optional[str] = None) -> bool:
        """Delete a user fact.
        
        Args:
            fact_id: The ID of the fact to delete.
            user_id: Optional user ID to override the instance user_id. 
        Returns:
            True if the fact was deleted, False otherwise.
        """
        # Resolve the user ID
        resolved_user_id = user_id if user_id is not None else self.user_id
        if not resolved_user_id:
            logger.error("User ID is required for deleting facts. No user ID provided.")
            return False
            
        # If user_id is different from self.user_id, we need to create a temporary path
        facts_file_path = self.facts_file
        if user_id and user_id != self.user_id:
            temp_path = os.path.join(self.db_path, user_id)
            facts_file_path = os.path.join(temp_path, "user_facts.json")
            if not os.path.exists(facts_file_path):
                logger.error(f"Facts file for user {user_id} not found at {facts_file_path}")
                return False
        
        # Load facts from the correct user file
        try:
            with open(facts_file_path, "r") as f:
                facts = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading facts for deletion: {e}")
            return False
        
        # Find and delete the fact
        original_length = len(facts)
        facts = [fact for fact in facts if fact["id"] != fact_id]
        
        # If no fact was removed, return False
        if len(facts) == original_length:
            logger.warning(f"Fact with ID {fact_id} not found for user {resolved_user_id}")
            return False
        
        # Save the updated facts back to the correct file
        try:
            with open(facts_file_path, "w") as f:
                json.dump(facts, f, indent=2)
            
            # Increment operations counter and check if rebuild is needed
            self.operations_counter += 1
            if self.operations_counter >= self.rebuild_threshold:
                logger.info(f"Operation threshold reached ({self.operations_counter}). Triggering vector database rebuild.")
                self.rebuild_vector_db()
                self.operations_counter = 0
            
            logger.info(f"Successfully deleted fact {fact_id} for user {resolved_user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving facts after deletion: {e}")
            return False
    
    def rebuild_vector_db(self) -> None:
        """Rebuild the vector database from scratch using the current facts in the JSON file.
        
        This removes any orphaned vectors from deleted facts.
        """
        try:
            logger.info("Rebuilding vector database...")
            
            # Get all current facts
            facts = self._load_facts()
            
            # Create a new vector database
            import os
            import shutil
            from app.database.vector_db import VectorDBInterface
            
            # Get the vector db path
            vector_db_path = os.path.join(self.db_path, "vector_db")
            
            # Create a backup of the old vector database (optional)
            backup_path = os.path.join(self.db_path, "vector_db_backup")
            if os.path.exists(vector_db_path):
                # Remove old backup if it exists
                if os.path.exists(backup_path):
                    shutil.rmtree(backup_path)
                # Create new backup
                shutil.copytree(vector_db_path, backup_path)
                # Remove old vector database
                shutil.rmtree(vector_db_path)
            
            # Initialize a new vector database
            self.vector_db = VectorDBInterface(
                db_path=vector_db_path
            )
            
            # Add all facts to the new vector database
            for fact in facts:
                try:
                    # Get embedding for the fact
                    embedding = get_embedding(fact["fact"])
                    
                    # Convert embedding to numpy array if it's a list
                    if isinstance(embedding, list):
                        embedding = np.array(embedding, dtype=np.float32)
                    
                    # Ensure the embedding is 2D
                    if len(embedding.shape) == 1:
                        embedding = embedding.reshape(1, -1)
                    
                    # Add to vector database
                    self.vector_db.add_vectors(
                        vectors=embedding,
                        metadata=[fact]
                    )
                except Exception as e:
                    logger.error(f"Error adding fact to vector database during rebuild: {e}")
            
            logger.info(f"Vector database rebuilt successfully with {len(facts)} facts")
        except Exception as e:
            logger.error(f"Error rebuilding vector database: {e}")
    
    def _load_facts(self) -> List[Dict[str, Any]]:
        """Load all facts from the JSON file.
        
        Returns:
            A list of all fact objects.
        """
        try:
            with open(self.facts_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_facts(self, facts: List[Dict[str, Any]]) -> None:
        """Save all facts to the JSON file.
        
        Args:
            facts: A list of fact objects to save.
        """
        with open(self.facts_file, "w") as f:
            json.dump(facts, f, indent=2) 