#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tool for accessing past conversations in the Move 37 application.
"""

from typing import Dict, Any, List, Optional
from langchain_community.tools import Tool
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
    def search_past_conversations(query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for past conversations by query similarity.
        
        Args:
            query: Query string to search for.
            user_id: User ID to filter by.
            limit: Maximum number of results to return.
            
        Returns:
            List of conversations ordered by relevance and in reverse-chronological order.
        """
        # Get the conversation database
        conversation_db = get_conversation_db()
        
        # Search for similar conversations
        results = conversation_db.search_conversations(query, k=limit)
        
        # Filter by user_id if provided
        if user_id:
            results = [r for r in results if r.get("user_id") == user_id]
        
        return results


# Create a tool for searching past conversations
conversation_search_tool = Tool(
    name="search_past_conversations",
    func=ConversationToolFunctions.search_past_conversations,
    description="Search for past conversations by query similarity. Returns conversations most similar to the query and ordered in reverse-chronological order."
)
