#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP (Model Context Protocol) server for Move37.
This server exposes tools and resources that can be used by the Thinker agent.
"""

import argparse
import logging
from fastmcp import FastMCP

from app.tools.math_tool import MathToolFunctions
from app.tools.conversation_tool import ConversationToolFunctions
from app.tools.file_search_tool import FileSearchToolFunctions
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
            result = MathToolFunctions.process_math_query(query)
            return result
        except Exception as e:
            logger.error(f"Error processing math query: {e}")
            return {"error": str(e)}
    
    # Resource for conversation history (replaces the tool)
    @mcp.resource(
        uri="conversations://{user_id}/recent-history",
        name="Recent Conversation History",
        description="Provides the past 2 days of conversation history for a user"
    )
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
                
            conversation_history = ConversationToolFunctions.get_recent_conversation_history(user_id=user_id)
            return conversation_history
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return {"error": str(e)}
    
    @mcp.tool()
    def search_for_past_conversations_with_query_similarity(query: str, user_id: str, limit: int = 1):
        """
        Search through the past conversations to find anything semantically similar to a query. 
        
        Args:
            query: Query string to search for
            user_id: User ID required for authentication
            limit: (Optional) Maximum number of results to return. Default is 1.
            
        Returns:
            List of conversations ordered by relevance and in reverse-chronological order
        """
        try:
            if not user_id:
                logger.error("No user_id provided for find_information_in_past_conversations")
                raise ValueError("user_id is required and cannot be empty")
                
            results = ConversationToolFunctions.search_for_past_conversations_with_query_similarity(query=query, user_id=user_id, limit=limit)
            return results
        except Exception as e:
            logger.error(f"Error searching conversations: {e}")
            return {"error": str(e)}
    
    @mcp.tool()
    def find_information_within_user_files(query: str, user_id: str):
        """
        Find specific information within the user's uploaded files
        
        Args:
            query: The information to find in the user's files
            user_id: User ID required for authentication
            
        Returns:
            An answer to the query based on information found in the user's files
        """
        try:
            if not user_id:
                logger.error("No user_id provided for find_information_from_files")
                raise ValueError("user_id is required and cannot be empty")
                
            result = FileSearchToolFunctions.find_information_within_user_files(query=query, user_id=user_id)
            return result
        except Exception as e:
            logger.error(f"Error finding information from files: {e}")  
            return {"error": str(e)}
    
    @mcp.tool()
    def get_file_content(file_name: str, user_id: str):
        """
        Retrieve the full content of a specific document.
        
        Args:
            file_name: Name of the file to retrieve
            user_id: User ID required for authentication
            
        Returns:
            The content of the file as text
        """
        try:
            if not user_id:
                logger.error("No user_id provided for get_file_content")
                raise ValueError("user_id is required and cannot be empty")
                
            content = FileSearchToolFunctions.get_file_content(file_name=file_name, user_id=user_id)
            return content
        except Exception as e:
            logger.error(f"Error retrieving file content: {e}")
            return {"error": str(e)}
    
    @mcp.tool()
    def list_user_files(user_id: str):
        """
        List all files uploaded by a user
        
        Args:
            user_id: User ID required for authentication
            
        Returns:
            Dictionary containing the list of files and their metadata
        """
        try:
            if not user_id:
                logger.error("No user_id provided for list_user_files")
                raise ValueError("user_id is required and cannot be empty")
                
            files = FileSearchToolFunctions.list_user_files(user_id=user_id)
            return files
        except Exception as e:
            logger.error(f"Error listing user files: {e}")
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
    
    try:
        mcp.run(transport=args.transport, host=args.host, port=args.port)
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        raise

if __name__ == "__main__":
    main() 