#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP (Model Context Protocol) server for Move37.
This server exposes tools and resources that can be used by the Thinker agent.
"""

import argparse
import asyncio
import logging
import os
from fastmcp import FastMCP

from app.tools.math_tool import MathToolFunctions
from app.tools.conversation_tool import ConversationToolFunctions
from app.tools.user_information_tool import get_user_preferences, get_user_facts_relevant_to_query
from app.core.config import MCP_SERVER_PORT, MCP_SERVER_HOST

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp_server")

def create_server():
    """Create and configure the MCP server."""
    # Create MCP server using the high-level FastMCP API
    mcp = FastMCP("Move37 MCP Server")
    
    @mcp.tool()
    def math_calculator(query: str):
        """
        Process a math query using the math tool from the application.
        
        Args:
            query: Math query to process
            

        Returns:
            The result of the calculation
        """
        try:
            logger.info(f"Processing math query: {query}")
            result = MathToolFunctions.process_math_query(query)
            return result
        except Exception as e:
            logger.error(f"Error processing math query: {e}")
            return {"error": str(e)}
    
    # Resource for conversation history (replaces the tool)
    @mcp.resource("conversations://{user_id}/recent-history")
    def recent_conversation_history(user_id: str):
        """
        Retrieve recent conversation history for a user over the past 2 days.
        
        Args:
            user_id: User ID required for authentication
            
        Returns:
            Recent conversation history of the user with various agents within the system
        """
        try:
            if not user_id:
                logger.error("No user_id provided for conversation history resource")
                return {"error": "user_id is required and cannot be empty"}
                
            logger.info(f"Retrieving conversation history for user '{user_id}'")
            conversation_history = ConversationToolFunctions.get_recent_conversation_history(user_id=user_id)
            return conversation_history
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return {"error": str(e)}
    
    @mcp.tool()
    def search_past_conversations(query: str, user_id: str, limit: int = 1):
        """
        Search for past conversations by query similarity.
        
        Args:
            query: Query string to search for
            user_id: User ID required for authentication
            limit: (Optional) Maximum number of results to return. Default is 1.
            
        Returns:
            List of conversations ordered by relevance and in reverse-chronological order
        """
        try:
            if not user_id:
                logger.error("No user_id provided for search_past_conversations")
                raise ValueError("user_id is required and cannot be empty")
                
            logger.info(f"Searching conversations with query '{query}' for user '{user_id}'")
            results = ConversationToolFunctions.search_past_conversations(query=query, user_id=user_id, limit=limit)
            return results
        except Exception as e:
            logger.error(f"Error searching conversations: {e}")
            return {"error": str(e)}

    # Resource for user preferences
    @mcp.resource("user://{user_id}/preferences")
    def user_preferences(user_id: str):
        """
        Retrieve user preferences from the database.
        
        Args:
            user_id: User ID required for authentication
            
        Returns:
            Formatted string containing the user's preferences
        """
        try:
            if not user_id:
                logger.error("No user_id provided for user preferences resource")
                return {"error": "user_id is required and cannot be empty"}
                
            logger.info(f"Retrieving preferences for user '{user_id}'")
            preferences = get_user_preferences(user_id=user_id)
            return preferences
        except Exception as e:
            logger.error(f"Error retrieving user preferences: {e}")
            return {"error": str(e)}

    @mcp.tool()
    def get_user_facts_relevant_to_query(query: str, user_id: str):
        """
        Search for facts relevant to a specific query from the user's database.
        
        Args:
            query: Query string to search for relevant facts
            user_id: User ID required for authentication
            
        Returns:
            Formatted string containing relevant facts about the user
        """
        try:
            if not user_id:
                logger.error("No user_id provided for get_user_facts_relevant_to_query")
                raise ValueError("user_id is required and cannot be empty")
                
            logger.info(f"Searching user facts with query '{query}' for user '{user_id}'")
            facts = get_user_facts_relevant_to_query(user_id=user_id, query=query)
            return facts
        except Exception as e:
            logger.error(f"Error retrieving user facts: {e}")
            return {"error": str(e)}
    
    return mcp

def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="Run the Move37 MCP server")
    parser.add_argument("--port", type=int, default=MCP_SERVER_PORT, help="Port to run the server on")
    parser.add_argument("--host", type=str, default=MCP_SERVER_HOST, help="Host to run the server on")
    parser.add_argument("--transport", type=str, choices=["sse", "websocket", "stdio"], default="sse", help="Transport type to use")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        # Set FastMCP debug logging
        logging.getLogger("fastmcp").setLevel(logging.DEBUG)
    
    # Create the server
    mcp = create_server()
    
    # Run the server with the specified transport
    logger.info(f"Starting FastMCP server on {args.host}:{args.port} with {args.transport} transport")
    
    try:
        mcp.run(transport=args.transport, host=args.host, port=args.port)
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        raise

if __name__ == "__main__":
    main() 