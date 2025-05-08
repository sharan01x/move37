#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP (Model Context Protocol) server for Move37.
This server exposes tools that can be used by the Thinker agent.
"""

import argparse
import asyncio
import logging
import os
from fastmcp import FastMCP

from app.tools.math_tool import MathToolFunctions
from app.tools.conversation_tool import ConversationToolFunctions
from app.database.conversation_db import ConversationDBInterface
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
    
    @mcp.tool()
    def get_past_conversations(user_id: str, days: int = 3):
        """
        Retrieve past conversations for a user over the specified number of days.
        
        Args:
            user_id: User ID required for authentication
            days: (Optional) Number of days of history to retrieve. By default, 3 days are retrieved.
            
        Returns:
            Recent conversation history of the user with various agents within the system
        """
        try:
            if not user_id:
                logger.error("No user_id provided for get_past_conversations")
                raise ValueError("user_id is required and cannot be empty")
                
            logger.info(f"Retrieving {days} days of conversation history for user '{user_id}'")
            conversation_db = ConversationDBInterface(user_id=user_id)
            conversation_history = conversation_db.get_recent_conversation_history(user_id=user_id, days=days)
            return conversation_history
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
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