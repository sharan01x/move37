#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Past Conversations database interface for the Move 37 application.
"""

import os
import numpy as np
import uuid
import json
import requests
import logging

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from functools import lru_cache

logger = logging.getLogger(__name__)

from app.core.config import (
    EMBEDDING_MODEL, 
    EMBEDDING_MODEL_DIMENSIONS,
    EMBEDDING_API_URL,
    CONVERSATIONS_VECTOR_DB_PATH
)
from app.database.vector_db_interface import VectorDBInterface
from app.models.conversation import PastConversation
from app.utils.date_utils import (
    format_for_storage,
    format_datetime_for_display,
    parse_datetime,
    standardize_timestamp
)


@lru_cache(maxsize=1)
def get_embeddings_model():
    """
    Get embeddings using the LLM API.
    """
    class EmbeddingsModel:
        def embed_query(self, text: str) -> List[float]:
            try:
                response = requests.post(
                    EMBEDDING_API_URL,
                    json={"model": EMBEDDING_MODEL, "prompt": text}
                )
                response.raise_for_status()
                return response.json()["embedding"]
            except Exception as e:
                print(f"Error getting embeddings: {e}")
                # Return a zero vector of the correct dimension as fallback
                return [0.0] * EMBEDDING_MODEL_DIMENSIONS
    
    return EmbeddingsModel()


class ConversationDBInterface(VectorDBInterface):
    def __init__(self, user_id: Optional[str] = None, dimension: int = EMBEDDING_MODEL_DIMENSIONS):
        """
        Initialize the past conversations database interface.
        
        Args:
            user_id: ID of the user whose conversations are being managed.
                    If provided, a user-specific subdirectory will be created.
            dimension: Dimension of the vectors. Default is defined in EMBEDDING_MODEL_DIMENSIONS config.
        """
        # Initialize the vector database with the conversations path from config
        super().__init__(db_path=CONVERSATIONS_VECTOR_DB_PATH, user_id=user_id, dimension=dimension)
        
        # Initialize embeddings model (cached)
        self.embeddings = get_embeddings_model()
        
        logger.info(f"Initialized ConversationDBInterface at path: {self.db_path}")
    

    
    def add_conversation(self, user_query: str, agent_response: str, agent_name: Optional[str] = None, timestamp: str = None, user_id: Optional[str] = None) -> str:
        """
        Add a complete conversation (user query + agent response) to the database.
        
        Args:
            user_query: The user's query
            agent_response: The agent's response
            agent_name: The name of the agent that provided the response
            timestamp: Timestamp string for when the conversation occurred (optional)
            user_id: The ID of the user who initiated the conversation (optional)
            
        Returns:
            ID of the added conversation
        """
        if not user_id:
            raise ValueError("user_id is required for storing conversations")
            
        # Generate a unique ID
        conversation_id = str(uuid.uuid4())
        
        try:
            # Generate embedding for the full conversation
            full_conversation = f"User: {user_query}\nAgent: {agent_response}"
            embedding = self.embeddings.embed_query(full_conversation)
            
            # Validate embedding dimensions
            expected_dim = EMBEDDING_MODEL_DIMENSIONS
            actual_dim = len(embedding)
            
            if actual_dim != expected_dim:
                # Adjust embedding to match expected dimensions (truncate or pad)
                if actual_dim > expected_dim:
                    embedding = embedding[:expected_dim]
                else:
                    embedding = np.pad(embedding, (0, expected_dim - actual_dim), 'constant')
            
            # Convert embedding to numpy array
            embedding_array = np.array([embedding], dtype=np.float32)
            
            # Set timestamp if not provided
            if timestamp is None:
                timestamp = format_for_storage()
            else:
                # Standardize any incoming timestamp format
                timestamp = standardize_timestamp(timestamp)
            
            # Create metadata
            metadata = {
                "id": conversation_id,
                "conversation": f"User: {user_query}\nAgent: {agent_response}",
                "timestamp": timestamp,
                "user_id": user_id
            }
            
            # Add agent_name to metadata if provided
            if agent_name:
                metadata["agent_name"] = agent_name
            
                # Store metadata directly in the user's folder
            metadata_file = os.path.join(self.db_path, f"{conversation_id}.json")
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f)
            
            # Add to vector database
            conversation_ids = self.add_vectors(
                vectors=embedding_array,
                metadata=[metadata]
            )
        except Exception as e:
            # Log the error but don't crash the application
            print(f"ERROR storing conversation in vector database: {e}", flush=True)
        
        # Return the conversation ID directly since we can't add to the vector database
        return conversation_id
    
    def search_conversations(self, query: str, k: int = 5, min_score: float = 0.0) -> List[Dict[str, Any]]:
        """
        Search for conversations by query using semantic search.
        
        Args:
            query: Query string.
            k: Number of results to return.
            min_score: Minimum similarity score (0-1) for results to be included.
            
        Returns:
            List of metadata for the k most similar conversations.
        """
        logger.info(f"Searching conversations with query: '{query}', user_id: '{self.user_id}'")
        
        # Use the base class semantic_search method
        results = self.semantic_search(
            query=query,
            embedding_function=self.embeddings.embed_query,
            top_k=k,
            filter_by_user=True,
            min_score=min_score
        )
        
        logger.info(f"Found {len(results)} relevant conversations")
        return results
    
    def get_recent_conversation_history(self, user_id: Optional[str] = None, days: int = 1) -> str:
        """
        Retrieve conversation history from the past N days formatted as a string.
        Uses direct database querying rather than semantic search for more reliable results.
        
        Args:
            user_id: Optional user ID to filter conversations. If None, returns all conversations.
            days: Number of days to look back (default 1)
            
        Returns:
            Formatted string containing recent conversation history.
        """
        logger.info(f"Getting recent conversation history for user: {user_id}, days: {days}")
        
        if not user_id:
            logger.warning("No user ID provided for conversation history")
            return "No user ID provided for conversation history."
            
        # Get the date range
        today = datetime.now().date()
        start_date = today - timedelta(days=days)
        logger.info(f"Looking for conversations from {start_date} to {today}")
        
        # Dictionary to store all conversations
        all_conversations = []
        
        # Check if user directory exists
        if not os.path.exists(self.db_path):
            logger.warning(f"No directory found for user {user_id} at: {self.db_path}")
            return f"No recent conversations found for user {user_id}."
        
        logger.info(f"Scanning directory: {self.db_path}")
        
        # Read through all metadata files to get conversations
        for filename in os.listdir(self.db_path):
            if not filename.endswith(".json"):
                continue
                
            file_path = os.path.join(self.db_path, filename)
            try:
                with open(file_path, 'r') as f:
                    metadata = json.load(f)
                    
                # Verify this conversation belongs to the requested user
                metadata_user_id = metadata.get("user_id")
                if metadata_user_id != user_id:
                    logger.debug(f"Skipping conversation with user_id: {metadata_user_id}, looking for: {user_id}")
                    continue
                    
                # Extract conversation information
                timestamp_str = metadata.get("timestamp", "")
                if not timestamp_str:
                    logger.debug(f"Skipping conversation with no timestamp")
                    continue
                    
                try:
                    # Parse the timestamp using our utility function
                    dt = parse_datetime(timestamp_str)
                    timestamp_date = dt.date()
                    
                    # If we successfully parsed the timestamp and it's in range
                    if timestamp_date >= start_date:
                        # Update the timestamp to our display format
                        metadata["timestamp"] = format_datetime_for_display(dt)
                        # Add the metadata to our list
                        all_conversations.append(metadata)
                        logger.debug(f"Added conversation from {timestamp_date} to history")
                    
                except Exception as e:
                    logger.error(f"Error parsing timestamp '{timestamp_str}': {e}")
                    continue
                    
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error reading metadata file {filename}: {e}")
                continue
        
        # Sort all conversations by timestamp
        all_conversations.sort(key=lambda x: parse_datetime(x.get("timestamp", "")))
        
        # Build the conversation history string
        if not all_conversations:
            return f"No relevant previous conversations found for user {user_id}."
            
        history = []
        for conv in all_conversations[-10:]:  # Get the last 10 conversations
            conversation = conv.get("conversation", "")
            timestamp = conv.get("timestamp", "Unknown date")
            agent_name = conv.get("agent_name", "Agent")  # Get the actual agent name
            
            # The conversation already contains "User: " and "Agent: " prefixes
            # So we don't need to add the agent name again, just the timestamp
            if conversation:
                # Split the conversation into user and agent parts
                parts = conversation.split("\nAgent: ")
                if len(parts) == 2:
                    user_part = parts[0].replace("User: ", "")
                    agent_part = parts[1]
                    
                    # Format with clear roles and timestamp, using the actual agent name
                    formatted_conversation = f"[{timestamp}]\nUser: {user_part}\nAgent {agent_name}: {agent_part}"
                    history.append(formatted_conversation)
                else:
                    # Fallback if the format is unexpected
                    formatted_conversation = f"[{timestamp}]\n{conversation}"
                    history.append(formatted_conversation)
        
        # Create a well-formatted conversation history string
        if history:
            formatted_history = "\n\n" + "\n\n".join(history)
            return formatted_history
        else:
            return f"No relevant previous conversations found for user {user_id}."
    
    def add_conversation_from_recall_response(self, user_id: str, query: str, recall_response: Dict[str, Any]) -> List[str]:
        """
        Add a conversation from a recall response by storing user query and agent response separately.
        
        Args:
            user_id: User ID.
            query: Original query.
            recall_response: Recall response dictionary.
            
        Returns:
            List of IDs for the added conversation entries or empty list if invalid response.
        """
        # Check if the response is valid
        if not recall_response.get("answer"):
            return []
        
        # Get timestamp in our standard format
        timestamp = format_for_storage()
        
        # Store user query and agent response together
        conversation_id = self.add_conversation(
            user_query=query,
            agent_response=recall_response["answer"],
            timestamp=timestamp,
            user_id=user_id
        )
        
        return [conversation_id]
