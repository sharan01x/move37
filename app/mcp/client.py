#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP client implementation for Move37.
Provides a client interface to connect to the MCP server and use its tools.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Callable

from fastmcp import Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Move37MCPClient:
    """Client for interacting with the Move37 MCP Server."""
    
    def __init__(self, host: str = "localhost", port: int = 7777):
        """Initialize the MCP client.
        
        Args:
            host: Host where the MCP server is running
            port: Port the MCP server is running on
        """
        self.host = host
        self.port = port
        self.client = None
        self.connected = False
        
        # Cache of available tools for quick lookup
        self.tool_cache = None
    
    async def _connect_async(self) -> bool:
        """Connect to the MCP server asynchronously.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Connect to the MCP server using SSE transport
            server_url = f"http://{self.host}:{self.port}/sse"
            self.client = Client(server_url)
            await self.client.__aenter__()
            
            self.connected = True
            logger.info(f"Connected to MCP server at {self.host}:{self.port}")
            
            # Get available tools
            await self._refresh_tool_cache_async()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            self.connected = False
            return False
    
    def connect(self) -> bool:
        """Connect to the MCP server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                logger.warning("Cannot use connect() inside a running event loop. Use connect_async() instead.")
                return False
            except RuntimeError:
                # No running event loop, we can create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self._connect_async())
        except Exception as e:
            logger.error(f"Error in connect(): {e}")
            return False
    
    async def connect_async(self) -> bool:
        """Connect to the MCP server from within an async context.
        
        This method should be used when already inside an async function.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            return await self._connect_async()
        except Exception as e:
            logger.error(f"Error in connect_async(): {e}")
            return False
    
    async def _disconnect_async(self) -> None:
        """Disconnect from the MCP server asynchronously."""
        if self.connected and self.client:
            try:
                await self.client.__aexit__(None, None, None)
                logger.info("Disconnected from MCP server")
            except Exception as e:
                logger.error(f"Error disconnecting from MCP server: {e}")
            finally:
                self.connected = False
                self.client = None
    
    def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self.connected:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._disconnect_async())
    
    async def _refresh_tool_cache_async(self) -> List[Dict[str, Any]]:
        """Refresh the cache of available tools asynchronously.
        
        Returns:
            List of available tools
        """
        try:
            if not self.connected:
                await self._connect_async()
            
            tools = await self.client.list_tools()
            self.tool_cache = tools
            logger.info(f"Retrieved {len(tools)} tools from MCP server")
            return tools
        except Exception as e:
            logger.error(f"Failed to get tools: {e}")
            return []
    
    def refresh_tool_cache(self) -> List[Dict[str, Any]]:
        """Refresh the cache of available tools.
        
        Returns:
            List of available tools
        """
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                logger.warning("Cannot use refresh_tool_cache() inside a running event loop. Use refresh_tool_cache_async() instead.")
                return []
            except RuntimeError:
                # No running event loop, we can create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(self._refresh_tool_cache_async())
        except Exception as e:
            logger.error(f"Error in refresh_tool_cache(): {e}")
            return []
    
    async def refresh_tool_cache_async(self) -> List[Dict[str, Any]]:
        """Refresh the cache of available tools from within an async context.
        
        This method should be used when already inside an async function.
        
        Returns:
            List of available tools
        """
        try:
            return await self._refresh_tool_cache_async()
        except Exception as e:
            logger.error(f"Error in refresh_tool_cache_async(): {e}")
            return []
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from the server.
        
        Returns:
            List of tool information dictionaries
        """
        if not self.tool_cache:
            return self.refresh_tool_cache()
        return self.tool_cache
    
    async def _call_tool_async(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool on the MCP server asynchronously.
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments for the tool
            
        Returns:
            Result of the tool call
        
        Raises:
            ValueError: If not connected to the server
        """
        if not self.connected:
            success = await self._connect_async()
            if not success:
                raise ValueError("Not connected to MCP server")
        
        try:
            logger.info(f"Calling tool {tool_name} with args: {kwargs}")
            result = await self.client.call_tool(tool_name, kwargs)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise ValueError(f"Failed to call tool {tool_name}: {e}")
    
    def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments for the tool
            
        Returns:
            Result of the tool call
        
        Raises:
            ValueError: If not connected to the server
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._call_tool_async(tool_name, **kwargs))
    
    # --- Convenience methods for specific tools ---
    
    def get_conversation_history(self, user_id: str, days: int = 2) -> Dict[str, Any]:
        """Get conversation history for a user.
        
        Args:
            user_id: User ID to get history for
            days: Number of days of history to retrieve
            
        Returns:
            Dictionary with conversation history
        """
        return self.call_tool("get_conversation_history", user_id=user_id, days=days)
    
    def solve_math_problem(self, query: str) -> Dict[str, Any]:
        """Solve a mathematical problem.
        
        Args:
            query: Math problem to solve
            
        Returns:
            Dictionary with solution
        """
        return self.call_tool("solve_math_problem", query=query)
    
    def get_user_facts(self, user_id: str, query: str, top_k: int = 10) -> Dict[str, Any]:
        """Get facts about a user based on a query.
        
        Args:
            user_id: User ID to get facts for
            query: Query to search for relevant facts
            top_k: Maximum number of facts to return
            
        Returns:
            Dictionary with relevant facts
        """
        return self.call_tool("get_user_facts", user_id=user_id, query=query, top_k=top_k)
    
    def get_all_user_facts(self, user_id: str) -> Dict[str, Any]:
        """Get all facts about a user.
        
        Args:
            user_id: User ID to get facts for
            
        Returns:
            Dictionary with all user facts
        """
        return self.call_tool("get_all_user_facts", user_id=user_id)
    
    def get_user_facts_by_category(self, user_id: str, category: str) -> Dict[str, Any]:
        """Get facts about a user in a specific category.
        
        Args:
            user_id: User ID to get facts for
            category: Category of facts to retrieve
            
        Returns:
            Dictionary with category-specific facts
        """
        return self.call_tool("get_user_facts_by_category", user_id=user_id, category=category)
    
    def search_user_files(self, user_id: str, query: str, document_name: str = "") -> Dict[str, Any]:
        """Search through a user's documents.
        
        Args:
            user_id: User ID to search files for
            query: Query to search for in documents
            document_name: Optional specific document to search in
            
        Returns:
            Dictionary with search results
        """
        return self.call_tool("search_user_files", user_id=user_id, query=query, document_name=document_name)
    
    def list_user_files(self, user_id: str) -> Dict[str, Any]:
        """List all documents available for a user.
        
        Args:
            user_id: User ID to list files for
            
        Returns:
            Dictionary with file list
        """
        return self.call_tool("list_user_files", user_id=user_id)
    
    def __del__(self):
        """Clean up connection when the client is destroyed."""
        try:
            if hasattr(self, 'connected') and self.connected:
                self.disconnect()
        except Exception as e:
            logger.error(f"Error in __del__: {e}")
            pass 