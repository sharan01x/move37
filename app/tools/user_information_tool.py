#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
User Information Tool for retrieving user preferences and relevant facts.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.database.user_facts_db import UserFactsDBInterface

logger = logging.getLogger(__name__)

def get_user_preferences(user_id: str) -> str:
    """Get formatted user preferences from the database.
    
    Args:
        user_id: The ID of the user whose preferences to retrieve.
        
    Returns:
        A formatted string containing the user's preferences, or a message if none found.
    """
    user_preferences = "No specific preferences found."
    try:
        # Create a user-specific instance
        user_specific_db = UserFactsDBInterface(user_id=user_id)
        
        # Get preferences from the database
        preference_facts = user_specific_db.get_facts_by_category("preference")
        
        if preference_facts:
            user_preferences = ""
            for i, pref in enumerate(preference_facts, 1):
                # Format the date
                created_date = ""
                try:
                    created_date = datetime.fromisoformat(pref['created_at']).strftime("%B %d, %Y")
                except (ValueError, KeyError):
                    created_date = "unknown date"
                user_preferences += f"{i}. {pref['fact']} (stated on {created_date})\n"
    except Exception as e:
        logger.error(f"Error fetching user preferences: {e}")
        user_preferences = "Could not retrieve user preferences due to an error."
        
    return user_preferences

def get_user_facts_relevant_to_query(user_id: str, query: str) -> str:
    """Get facts relevant to a specific query from the user's database.
    
    Args:
        user_id: The ID of the user whose facts to search.
        query: The query to search for relevant facts.
        
    Returns:
        A formatted string containing relevant facts, or a message if none found.
    """
    try:
        # Create a user-specific instance
        user_specific_db = UserFactsDBInterface(user_id=user_id)
        
        # Log the search attempt
        logger.info(f"Searching for facts relevant to: {query}")
        
        # Search for relevant facts using semantic search
        relevant_facts = user_specific_db.semantic_search(query, top_k=10)
        logger.info(f"Found {len(relevant_facts)} facts relevant to the query using semantic search")
        
        # If no facts found, try to search with a more general query
        if not relevant_facts:
            # Extract key terms from the query to broaden the search
            import re
            key_terms = re.findall(r'\b\w{4,}\b', query.lower())
            if key_terms:
                for term in key_terms:
                    logger.info(f"Searching with broader term: {term}")
                    additional_facts = user_specific_db.semantic_search(term, top_k=3)
                    relevant_facts.extend(additional_facts)
                    logger.info(f"Found {len(additional_facts)} additional facts with term: {term}")
            
            # If still no facts, fall back to getting a subset of all facts
            if not relevant_facts:
                logger.info("No relevant facts found, falling back to a subset of all facts")
                all_facts = user_specific_db.get_all_facts()
                # Take the most recent facts (up to 50)
                relevant_facts = sorted(all_facts, key=lambda x: x.get('created_at', ''), reverse=True)[:50]
                logger.info(f"Using {len(relevant_facts)} recent facts as fallback")
        
        # Format facts for the prompt
        facts_context = "No relevant facts found about the user found"
        if relevant_facts:
            facts_context = ""
            for i, fact in enumerate(relevant_facts, 1):
                # Format the date
                created_date = ""
                try:
                    created_date = datetime.fromisoformat(fact['created_at']).strftime("%B %d, %Y")
                except (ValueError, KeyError):
                    created_date = "unknown date"
                
                facts_context += f"{i}. {fact['fact']} (learned on {created_date})\n"
        else:
            facts_context = "No relevant facts found about the user."
            
        return facts_context
        
    except Exception as e:
        logger.error(f"Error retrieving user facts: {e}")
        return "Could not retrieve user facts due to an error."
