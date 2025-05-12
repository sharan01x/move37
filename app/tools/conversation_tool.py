#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tool for accessing past conversations in the Move 37 application.
"""

from typing import Dict, Any, List, Optional
from functools import lru_cache

from app.database.conversation_db import ConversationDBInterface


@lru_cache(maxsize=1)
def get_conversation_db():
    """
    Get a singleton instance of ConversationDBInterface.
    
    Returns:
        An instance of ConversationDBInterface.
    """
    return ConversationDBInterface()


class ConversationToolFunctions:
    """Function implementations for the conversation tool."""
    
    @staticmethod
    def get_recent_conversation_history(user_id: str, days: int = 2) -> str:
        """
        Retrieve past conversations for a user over the specified number of days.
        
        Args:
            user_id: User ID required for authentication
            days: (Optional) Number of days of history to retrieve. Default is 2 days.
            
        Returns:
            Recent conversation history of the user with various agents within the system
        """
        if not user_id:
            raise ValueError("user_id is required and cannot be empty")
            
        # Create a user-specific instance to ensure we're looking in the right folder
        conversation_db = ConversationDBInterface(user_id=user_id)
        
        # Get the conversation history
        conversation_history = conversation_db.get_recent_conversation_history(
            user_id=user_id, 
            days=days
        )
        
        return conversation_history
    
    @staticmethod
    def search_for_past_conversations_with_query_similarity(query: str, user_id: str, limit: int = 1) -> List[Dict[str, Any]]:
        """
        Search for past conversations by query similarity.
        
        Args:
            query: Query string to search for.
            user_id: User ID to filter by.
            limit: (Optional) Maximum number of results to return. Default is 1.
            
        Returns:
            List of conversations ordered by relevance and in reverse-chronological order.
        """
        if not user_id:
            raise ValueError("user_id is required and cannot be empty")
            
        # Create a user-specific instance to handle the search properly
        temp_db = ConversationDBInterface(user_id=user_id)
        results = temp_db.search_conversations(query, k=limit)
            
        return results
        
