#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP server implementation for Move37.
Provides tools for the RecallAgent to use via the Model Context Protocol.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Callable

from fastmcp import FastMCP

# Import Move37 utilities and interfaces
from app.database.conversation_db import ConversationDBInterface
from app.database.user_facts_db import UserFactsDBInterface
from app.database.file_db import FileDBInterface
from app.utils.file_vectorizer import FileVectorizer
from app.tools.math_tool import math_tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the MCP server
mcp = FastMCP("Move37")

# Add startup verification
logger.info("Initializing Move37 MCP Server with tools")

# --- First Responder Tool Implementations ---

@mcp.tool()
def get_conversation_history(user_id: str, days: int = 3) -> Dict[str, Any]:
    """Retrieve recent conversation history for a user.
    
    Args:
        user_id: User ID to get history for
        days: Number of days of history to retrieve
        
    Returns:
        Dictionary with conversation history or error message
    """
    try:
        logger.info(f"Retrieving {days} days of conversation history for user: {user_id}")
        conversation_db = ConversationDBInterface(user_id=user_id)
        conversation_history = conversation_db.get_recent_conversation_history(user_id=user_id, days=days)
        
        return {
            "success": True,
            "conversation_history": conversation_history
        }
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# --- Number Ninja Tool Implementations ---

@mcp.tool()
def solve_math_problem(query: str) -> Dict[str, Any]:
    """Solve a mathematical problem or equation.
    
    Args:
        query: Math problem or equation to solve
        
    Returns:
        Dictionary with solution or error message
    """
    try:
        logger.info(f"Solving math problem: {query}")
        result = math_tool.func(query)
        
        return {
            "success": True,
            "is_math_query": result.get("is_math_tool_query", False),
            "answer": result.get("answer"),
            "requires_llm": result.get("requires_llm", False)
        }
    except Exception as e:
        logger.error(f"Error solving math problem: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# --- Persephone Tool Implementations ---

@mcp.tool()
def get_user_facts(user_id: str, query: str, top_k: int = 10) -> Dict[str, Any]:
    """Retrieve facts about a user based on a semantic search.
    
    Args:
        user_id: User ID to get facts for
        query: Query to search for relevant facts
        top_k: Maximum number of facts to return
        
    Returns:
        Dictionary with relevant facts or error message
    """
    try:
        logger.info(f"Searching for user facts: {query} (user: {user_id})")
        # Create a user-specific instance to ensure we're looking in the right folder
        user_facts_db = UserFactsDBInterface(user_id=user_id)
        
        # Use semantic search to find relevant facts
        relevant_facts = user_facts_db.semantic_search(query, top_k=top_k)
        
        return {
            "success": True,
            "relevant_facts": relevant_facts,
            "count": len(relevant_facts)
        }
    except Exception as e:
        logger.error(f"Error retrieving user facts: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
def get_all_user_facts(user_id: str) -> Dict[str, Any]:
    """Retrieve all facts about a user.
    
    Args:
        user_id: User ID to get facts for
        
    Returns:
        Dictionary with all user facts or error message
    """
    try:
        logger.info(f"Retrieving all facts for user: {user_id}")
        # Create a user-specific instance to ensure we're looking in the right folder
        user_facts_db = UserFactsDBInterface(user_id=user_id)
        
        # Get all facts
        facts = user_facts_db.get_all_facts(user_id=user_id)
        
        return {
            "success": True,
            "facts": facts,
            "count": len(facts)
        }
    except Exception as e:
        logger.error(f"Error retrieving all user facts: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
def get_user_facts_by_category(user_id: str, category: str) -> Dict[str, Any]:
    """Retrieve facts about a user in a specific category.
    
    Args:
        user_id: User ID to get facts for
        category: Category of facts to retrieve
        
    Returns:
        Dictionary with category-specific facts or error message
    """
    try:
        logger.info(f"Retrieving {category} facts for user: {user_id}")
        # Create a user-specific instance to ensure we're looking in the right folder
        user_facts_db = UserFactsDBInterface(user_id=user_id)
        
        # Get facts by category
        facts = user_facts_db.get_facts_by_category(category=category, user_id=user_id)
        
        return {
            "success": True,
            "category": category,
            "facts": facts,
            "count": len(facts)
        }
    except Exception as e:
        logger.error(f"Error retrieving category facts: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# --- Librarian Tool Implementations ---

@mcp.tool()
def search_user_files(user_id: str, query: str, document_name: str = "") -> Dict[str, Any]:
    """Search through a user's documents for relevant information.
    
    Args:
        user_id: User ID to search files for
        query: Query to search for in documents
        document_name: Optional specific document to search in
        
    Returns:
        Dictionary with search results or error message
    """
    try:
        logger.info(f"Searching files for: '{query}' (user: {user_id}, document: '{document_name}')")
        
        # Get vectorizer for this user
        vectorizer = FileVectorizer(user_id=user_id)
        file_db = FileDBInterface(user_id=user_id)
        
        # Check if we have any files
        metadata_file_path = f"data/files/{user_id}/file_metadata.json"
        
        if not os.path.exists(metadata_file_path):
            return {
                "success": False,
                "message": "No files found for this user"
            }
        
        # Load file metadata
        with open(metadata_file_path, 'r') as f:
            all_files_metadata = json.load(f)
        
        # If a specific document is requested, verify it exists
        if document_name:
            document_exists = any(file.get('file_name') == document_name for file in all_files_metadata)
            if not document_exists:
                return {
                    "success": False,
                    "message": f"Document '{document_name}' not found"
                }
        
        # Perform search
        search_results = vectorizer.search(query, limit=50)
        
        # Filter to document if specified
        if document_name:
            search_results = [result for result in search_results if result.get('file_name') == document_name]
        
        # If no results, return early
        if not search_results:
            return {
                "success": True,
                "message": "No relevant information found",
                "results": []
            }
        
        # Process results
        processed_results = []
        
        # Group results by document
        documents = {}
        for result in search_results:
            file_name = result.get('file_name')
            if file_name not in documents:
                documents[file_name] = []
            documents[file_name].append(result)
        
        # For each document, compile the most relevant chunks
        for doc_name, chunks in documents.items():
            # Sort by relevance (distance)
            chunks.sort(key=lambda x: x.get('distance', 1000.0))
            
            # Take top chunks (limited to avoid excessive content)
            top_chunks = chunks[:5]
            
            # Compile text
            text_content = "\n\n".join([chunk.get('chunk_text', '') for chunk in top_chunks])
            
            processed_results.append({
                "document_name": doc_name,
                "content": text_content,
                "relevance_score": 1.0 / (1.0 + top_chunks[0].get('distance', 1.0))
            })
        
        # Sort processed results by relevance
        processed_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return {
            "success": True,
            "message": f"Found relevant information in {len(processed_results)} documents",
            "results": processed_results
        }
        
    except Exception as e:
        logger.error(f"Error searching user files: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
def list_user_files(user_id: str) -> Dict[str, Any]:
    """List all documents available for a user.
    
    Args:
        user_id: User ID to list files for
        
    Returns:
        Dictionary with file list or error message
    """
    try:
        logger.info(f"Listing files for user: {user_id}")
        file_db = FileDBInterface(user_id=user_id)
        
        # Get all files
        files = file_db.list_files()
        
        return {
            "success": True,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        logger.error(f"Error listing user files: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def start_server(port: int = 7777):
    """Start the MCP server on the specified port."""
    # Verify tools are registered before starting the server
    try:
        # Create a new event loop to run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Define an async function to get the tools
        async def get_tools_async():
            return await mcp.get_tools()
        
        # Run the async function in the event loop
        tools = loop.run_until_complete(get_tools_async())
        loop.close()
        
        logger.info(f"Starting Move37 MCP Server on port {port} with {len(tools)} registered tools")
        if not tools:
            logger.warning("No tools registered with the MCP server! Check implementation.")
        else:
            for tool in tools:
                logger.info(f"  - Registered tool: {tool}")
    except Exception as e:
        logger.error(f"Error checking registered tools: {e}")
        logger.info(f"Starting Move37 MCP Server on port {port}")
    
    # Add a health check endpoint to the FastAPI app
    @mcp.app.get("/health")
    async def health_check():
        """Simple health check endpoint for the MCP server."""
        return {"status": "ok", "service": "Move37 MCP Server"}
    
    # When running from another Python script, we can specify the SSE transport
    mcp.run(transport="sse", port=port)

@mcp.tool()
def debug_server_status() -> Dict[str, Any]:
    """Get the current status of the MCP server and list of available tools.
    This tool is for debugging purposes only.
    
    Returns:
        Dictionary with server status information
    """
    try:
        # Create a new event loop to run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Define an async function to get the tools
        async def get_tools_async():
            return await mcp.get_tools()
        
        # Run the async function in the event loop
        tools = loop.run_until_complete(get_tools_async())
        loop.close()
        
        return {
            "success": True,
            "server": "Move37 MCP Server",
            "status": "running",
            "tools_count": len(tools),
            "tools": tools
        }
    except Exception as e:
        logger.error(f"Error in debug_server_status: {e}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    start_server() 