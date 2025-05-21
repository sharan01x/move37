#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP (Model Context Protocol) server for Move37.
This server exposes tools and resources that can be used by the Thinker agent.
"""

import argparse
import logging
from datetime import datetime
from fastmcp import FastMCP

from app.tools.math_tool import MathToolFunctions
from app.tools.conversation_tool import ConversationToolFunctions
from app.tools.file_search_tool import FileSearchToolFunctions
from app.tools.browser_tool import run_browser_task
from app.tools.web_search_tool import WebSearchTool
from app.core.config import MCP_SERVER_PORT, MCP_SERVER_HOST

# Set up logging with reduced noise
logging.basicConfig(
    level=logging.WARNING,  # Changed from INFO to WARNING
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp_server")

# Reduce noise from uvicorn and fastapi
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logging.getLogger("fastmcp").setLevel(logging.WARNING)

def create_server():
    """Create and configure the MCP server."""
    # Create MCP server using the high-level FastMCP API
    mcp = FastMCP("Move37 MCP Server")
    
    @mcp.tool()
    async def execute_browser_task(task: str, user_id: str):
        """
        Use this tool to use a web browser to perform tasks on the web for real-time information or actions.
        
        Args:
            task: The task description for the browser to execute.
            user_id: User ID (currently not used by the browser tool directly, but good for consistency).
            
        Returns:
            The result of the browser task, or an error message.
        """
        logger.info(f"MCP Server received browser task: '{task}' for user_id: {user_id}")
        try:
            # Pass both task and user_id to run_browser_task
            result = await run_browser_task(task=task, user_id=user_id)
            return result
        except Exception as e:
            logger.error(f"Error executing browser task via MCP: {e}", exc_info=True)
            return {"error": f"MCP Server Error: Failed to execute browser task. {str(e)}"}

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
        Retrieve recent conversation history for a user over the past 2 days. Use this when you need the context of recent conversations with the user.
        
        Args:
            user_id: User ID required for authentication
            
        Returns:
            Recent conversation history of the user with various agents within the system
        """
        try:
            if not user_id:
                logger.error("No user_id provided for conversation history resource")
                return {"error": "user_id is required and cannot be empty"}
                
            conversation_history = ConversationToolFunctions.get_recent_conversation_history(user_id=user_id, days=2)
            return conversation_history
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}")
            return {"error": str(e)}
    
    @mcp.tool()
    def find_information_in_past_conversations(query: str, user_id: str, limit: int = 1):
        """
        This is useful when you need to find information about a specific topic or idea that the user has mentioned in the past.
        
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
    
    @mcp.tool()
    def get_historical_conversations(user_id: str, start_date_time: str, end_date_time: str):
        """
        Retrieve conversation history between specific start and end dates and times.
        
        Args:
            user_id: User ID required for authentication
            start_date_time: Start datetime in ISO format (e.g., "2024-01-01T00:00:00")
            end_date_time: End datetime in ISO format (e.g., "2024-01-31T23:59:59")
            
        Returns:
            Conversation history within the specified date range
        """
        try:
            if not user_id:
                logger.error("No user_id provided for historical conversation history")
                return {"error": "user_id is required and cannot be empty"}
            
            # Parse the datetime strings
            try:
                # Try parsing with ISO format first
                try:
                    start_dt = datetime.fromisoformat(start_date_time)
                    end_dt = datetime.fromisoformat(end_date_time)
                except ValueError:
                    # If ISO format fails, try parsing with date only format
                    try:
                        start_dt = datetime.strptime(start_date_time, "%Y-%m-%d")
                        end_dt = datetime.strptime(end_date_time, "%Y-%m-%d")
                        # Set end time to end of day if only date provided
                        end_dt = end_dt.replace(hour=23, minute=59, second=59)
                    except ValueError as e:
                        raise ValueError(f"Invalid datetime format. Please use ISO format (YYYY-MM-DDTHH:MM:SS) or date format (YYYY-MM-DD): {str(e)}")
            except ValueError as e:
                logger.error(f"Invalid datetime format: {e}")
                return {"error": f"Invalid datetime format. Please use ISO format (YYYY-MM-DDTHH:MM:SS): {str(e)}"}
            
            # Get the conversation history
            history = ConversationToolFunctions.get_historical_conversation_history(
                user_id=user_id,
                start_date_time=start_dt,
                end_date_time=end_dt
            )
            
            return history
            
        except Exception as e:
            logger.error(f"Error retrieving historical conversation history: {e}")
            return {"error": str(e)}
        # Example integration with MCP server (server.py)
    
    # Web search tool integration
    @mcp.tool()
    def web_search(query: str, user_id: str, max_results: int = 3, enable_citations: bool = True):
        """
        Perform a web search using the provided query. Use this when you need to find information from the web, not to perform actions on websites.
        
        Args:
            query: The search query
            user_id: User ID required for authentication
            max_results: (Optional) Maximum number of search results to return. Default is 3.
            enable_citations: (Optional) Whether to include citations in the response. Default is True.
            
        Returns:
            Search results from the web with citations when enabled
        """
        try:
            if not user_id:
                logger.error("No user_id provided for web search")
                raise ValueError("user_id is required and cannot be empty")
            
            # Initialize the tool
            web_search_tool = WebSearchTool()
            
            # Perform the search
            results = web_search_tool.search(
                query=query, 
                max_results=max_results,
                enable_citations=enable_citations
            )
            
            return results
        
        except Exception as e:
            logger.error(f"Error performing web search: {e}")
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