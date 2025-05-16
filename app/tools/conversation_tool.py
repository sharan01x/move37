#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tool for accessing past conversations in the Move 37 application.
"""

from typing import Dict, Any, List, Optional
from functools import lru_cache
from datetime import datetime
import logging

from app.database.conversation_db import ConversationDBInterface

logger = logging.getLogger(__name__)


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
    def get_historical_conversation_history(user_id: str, start_date_time: datetime, end_date_time: datetime) -> str:
        """
        Get conversation history between specific start and end datetimes.
        
        Args:
            user_id: The ID of the user whose conversations to retrieve
            start_date_time: Start datetime for the history range
            end_date_time: End datetime for the history range
            
        Returns:
            Formatted string containing conversation history within the specified range
        """
        try:
            # Initialize the conversation database interface
            db = ConversationDBInterface(user_id=user_id)
            
            # Get the conversation history using the date range function
            history = db.get_conversation_history_by_date_range(
                user_id=user_id,
                start_datetime=start_date_time,
                end_datetime=end_date_time
            )
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving historical conversation history: {e}")
            return f"Error retrieving conversation history: {str(e)}"
    
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
        
