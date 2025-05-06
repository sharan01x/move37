#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Recall Agent for the Move 37 application.
A unified agent that replaces specialized agents by using MCP tools.
This implementation makes direct LLM calls and follows MCP principles by allowing
the LLM to decide which tools to use.
"""

import os
import json
import re
import asyncio
import logging
import requests
from typing import Dict, Any, List, Optional, Union, Callable
import time

from app.core.config import CHAT_API_URL, RECALL_LLM_MODEL
from app.mcp.client import Move37MCPClient
from app.database.conversation_db import ConversationDBInterface
from app.database.user_facts_db import UserFactsDBInterface
from app.database.file_db import FileDBInterface
from app.utils.file_vectorizer import FileVectorizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecallAgent:
    """
    Unified agent that replaces specialized agents by using MCP tools.
    Uses MCP tools through an LLM that decides which tools to use and when.
    """
    
    def __init__(self, mcp_host: str = "localhost", mcp_port: int = 7777):
        """Initialize the Recall agent with MCP client.
        
        Args:
            mcp_host: Host where the MCP server is running
            mcp_port: Port the MCP server is running on
        """
        self.name = "Recall"
        self.description = "I am a unified agent that can answer all types of questions using specialized tools."
        self.role = "Universal Assistant"
        self.goal = "Provide accurate and helpful responses to user queries using the appropriate tools."
        
        # For status message callbacks
        self.message_callback = None
        
        # Initialize MCP client
        self.mcp_client = Move37MCPClient(host=mcp_host, port=mcp_port)
        
        # We'll use empty tools list first, and try to load them
        self.available_tools = []
        
        # Connect to MCP server and get available tools - with retries
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries and not self.available_tools:
            try:
                # Try to connect to the MCP server
                logger.info(f"Attempting to connect to MCP server (retry {retry_count + 1}/{max_retries})...")
                connection_success = self.mcp_client.connect()
                
                if not connection_success:
                    logger.warning(f"Failed to connect to MCP server on attempt {retry_count + 1}")
                    retry_count += 1
                    if retry_count < max_retries:
                        # Wait a bit before retrying
                        time.sleep(1)
                    continue
                    
                # If connection was successful, get available tools
                self.available_tools = self.mcp_client.get_available_tools()
                logger.info(f"Connected to MCP server with {len(self.available_tools)} available tools")
                
                # Check if tools were actually loaded
                if not self.available_tools:
                    logger.warning("No tools were loaded from the MCP server. Trying to refresh tool cache...")
                    # Try to refresh the tool cache
                    self.available_tools = self.mcp_client.refresh_tool_cache()
                    
                    if not self.available_tools:
                        logger.warning("Still no tools available after refresh. Will try again or continue without tools.")
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(1)
                        continue
                
                # If we get here with tools, break the retry loop
                if self.available_tools:
                    logger.info(f"Successfully loaded {len(self.available_tools)} tools")
                    break
                    
            except Exception as e:
                logger.error(f"Error connecting to MCP server (attempt {retry_count + 1}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1)
        
        # If we still have no tools after retries, log a warning
        if not self.available_tools:
            logger.warning("Failed to load tools after multiple attempts. RecallAgent will have limited functionality.")
    
    def set_message_callback(self, callback: Optional[Callable] = None) -> None:
        """Set the message callback function.
        
        Args:
            callback: Callback function for sending interim messages
        """
        self.message_callback = callback
    
    async def send_message(self, message: str) -> None:
        """Send a status message via the callback if available.
        
        Args:
            message: Message to send
        """
        if self.message_callback:
            await self.message_callback(message)
    
    def format_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Format available MCP tools for the LLM's function calling format.
        
        Returns:
            List of tool definitions in the format expected by LLM function calling
        """
        formatted_tools = []
        
        for tool in self.available_tools:
            # Handle different tool object structures (dict or Pydantic model)
            if hasattr(tool, 'get') and callable(tool.get):
                # Dictionary-like object
                tool_name = tool.get("name", "")
                tool_description = tool.get("description", "")
                tool_parameters = tool.get("parameters", {})
            else:
                # Pydantic model or object with attributes
                tool_name = getattr(tool, "name", "")
                tool_description = getattr(tool, "description", "")
                tool_parameters = getattr(tool, "parameters", {})
            
            formatted_tool = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # Add parameters
            for param_name, param_info in tool_parameters.items():
                formatted_tool["function"]["parameters"]["properties"][param_name] = {
                    "type": param_info.get("type", "string") if hasattr(param_info, "get") else getattr(param_info, "type", "string"),
                    "description": param_info.get("description", "") if hasattr(param_info, "get") else getattr(param_info, "description", "")
                }
                
                # If it doesn't have a default value, it's required
                if not (hasattr(param_info, "get") and "default" in param_info) and not hasattr(param_info, "default"):
                    formatted_tool["function"]["parameters"]["required"].append(param_name)
            
            formatted_tools.append(formatted_tool)
        
        return formatted_tools
    
    async def call_llm_with_tools(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> Dict[str, Any]:
        """Make an LLM call with tool definitions for function calling.
        
        Args:
            messages: List of message dictionaries for the conversation
            temperature: Temperature for response generation
            
        Returns:
            The LLM's response as a dictionary
        """
        try:
            # Format tools for the LLM
            tools = self.format_tools_for_llm()
            
            # Prepare the payload with tools
            payload = {
                "model": RECALL_LLM_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature
                },
                "tools": tools
            }
            
            # Make the API call
            response = requests.post(CHAT_API_URL, json=payload)
            response.raise_for_status()
            
            # Return the full response
            return response.json()
            
        except Exception as e:
            logger.error(f"Error calling LLM with tools: {e}")
            raise
    
    async def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call from the LLM.
        
        Args:
            tool_call: Tool call dictionary from the LLM
            
        Returns:
            Result of the tool call
        """
        try:
            function_call = tool_call.get("function", {})
            tool_name = function_call.get("name", "")
            
            # Parse arguments
            args_str = function_call.get("arguments", "{}")
            try:
                # Check if args_str is already a dict (handle different formats)
                if isinstance(args_str, dict):
                    args = args_str
                else:
                    args = json.loads(args_str)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse tool arguments: {args_str}")
                return {
                    "success": False,
                    "error": f"Invalid arguments format: {args_str}"
                }
            
            # Special handling for conversation history to ensure at least 2 days
            if tool_name == "get_conversation_history" and "days" in args:
                if args["days"] < 2:
                    args["days"] = 2
            
            # Check if we need to reconnect before calling the tool
            if not self.mcp_client.connected:
                connection_success = await self.mcp_client.connect_async()
                if not connection_success:
                    return {
                        "success": False,
                        "error": "Failed to connect to MCP server for tool execution"
                    }
            
            # Call the tool using the appropriate async method
            await self.send_message(f"Using tool: {tool_name} to find information...")
            
            # Direct async tool calling based on tool name
            result = await self._call_tool_async(tool_name, args)
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool call: {e}")
            return {
                "success": False,
                "error": f"Tool execution error: {str(e)}"
            }
    
    async def _call_tool_async(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool asynchronously in a way that's safe inside an event loop.
        
        Args:
            tool_name: Name of the tool to call
            args: Arguments for the tool
            
        Returns:
            Tool execution result
        """
        try:
            # Handle each tool type directly with async-safe logic
            if tool_name == "get_conversation_history":
                user_id = args.get("user_id", "")
                days = args.get("days", 2)
                
                # Call directly to the DB interface to avoid event loop issues
                conversation_db = ConversationDBInterface(user_id=user_id)
                conversation_history = conversation_db.get_recent_conversation_history(user_id=user_id, days=days)
                return {
                    "success": True,
                    "conversation_history": conversation_history
                }
                
            elif tool_name == "get_user_facts":
                user_id = args.get("user_id", "")
                query = args.get("query", "")
                top_k = args.get("top_k", 10)
                
                # Direct DB access
                user_facts_db = UserFactsDBInterface(user_id=user_id)
                relevant_facts = user_facts_db.semantic_search(query, top_k=top_k)
                return {
                    "success": True,
                    "relevant_facts": relevant_facts,
                    "count": len(relevant_facts)
                }
                
            elif tool_name == "get_all_user_facts":
                user_id = args.get("user_id", "")
                
                # Direct DB access
                user_facts_db = UserFactsDBInterface(user_id=user_id)
                facts = user_facts_db.get_all_facts(user_id=user_id)
                return {
                    "success": True,
                    "facts": facts,
                    "count": len(facts)
                }
                
            elif tool_name == "get_user_facts_by_category":
                user_id = args.get("user_id", "")
                category = args.get("category", "")
                
                # Direct DB access
                user_facts_db = UserFactsDBInterface(user_id=user_id)
                facts = user_facts_db.get_facts_by_category(category=category, user_id=user_id)
                return {
                    "success": True,
                    "category": category,
                    "facts": facts,
                    "count": len(facts)
                }
                
            elif tool_name == "solve_math_problem":
                query = args.get("query", "")
                
                # Direct math tool access
                from app.tools.math_tool import math_tool
                result = math_tool.func(query)
                return {
                    "success": True,
                    "is_math_query": result.get("is_math_tool_query", False),
                    "answer": result.get("answer"),
                    "requires_llm": result.get("requires_llm", False)
                }
                
            elif tool_name == "search_user_files":
                user_id = args.get("user_id", "")
                query = args.get("query", "")
                document_name = args.get("document_name", "")
                
                # Direct file vectorizer access
                vectorizer = FileVectorizer(user_id=user_id)
                file_db = FileDBInterface(user_id=user_id)
                
                # Rest of the file search logic as in the server.py implementation
                # (simplified for brevity - we would need to implement the complete logic)
                search_results = vectorizer.search(query, limit=50)
                if document_name:
                    search_results = [r for r in search_results if r.get('file_name') == document_name]
                
                # Process results (simplified)
                return {
                    "success": True,
                    "message": f"Found {len(search_results)} results",
                    "results": search_results[:5]  # Limit to 5 results
                }
                
            elif tool_name == "list_user_files":
                user_id = args.get("user_id", "")
                
                # Direct file DB access
                file_db = FileDBInterface(user_id=user_id)
                files = file_db.list_files()
                
                return {
                    "success": True,
                    "files": files,
                    "count": len(files)
                }
                
            elif tool_name == "debug_server_status":
                # Simplified version of the server status
                return {
                    "success": True,
                    "server": "Move37 MCP Server",
                    "status": "running",
                    "tools_count": len(self.available_tools),
                    "accessed_directly": True
                }
                
            else:
                # For unknown tools, fall back to trying the client call
                try:
                    # Try async client call if available
                    if hasattr(self.mcp_client, "_call_tool_async"):
                        logger.info(f"Using async client call for {tool_name}")
                        return await self.mcp_client._call_tool_async(tool_name, args)
                    else:
                        # Fall back to sync call but with warning
                        logger.warning(f"Falling back to sync client call for {tool_name} - may cause event loop issues")
                        return self.mcp_client.call_tool(tool_name, **args)
                except Exception as e:
                    logger.error(f"Failed calling unknown tool {tool_name}: {e}")
                    return {
                        "success": False,
                        "error": f"Unknown tool or execution error: {str(e)}"
                    }
                
        except Exception as e:
            logger.error(f"Error in _call_tool_async for {tool_name}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"Tool execution error: {str(e)}"
            }
    
    async def answer_query_async(self, query: str, user_id: str, message_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Answer a query using MCP tools, allowing the LLM to decide which tools to use.
        This is the async version that should be used when called from an async context.
        
        Args:
            query: Query to answer
            user_id: User ID making the query
            message_callback: Optional callback function to send interim messages during processing
            
        Returns:
            Dictionary containing the formatted response
        """
        try:
            # Set message callback
            self.set_message_callback(message_callback)
            
            # Send initial status message
            await self.send_message("Asking around...")
            
            # Check if MCP server is connected and has tools
            if not self.available_tools:
                # Try to reconnect and refresh tools using async methods
                try:
                    connection_success = await self.mcp_client.connect_async()
                    if connection_success:
                        self.available_tools = await self.mcp_client.refresh_tool_cache_async()
                except Exception as e:
                    logger.error(f"Failed to reconnect to MCP server asynchronously: {e}")
            
            # Check if tools are available - if not, log a warning but continue
            if not self.available_tools:
                logger.warning("No tools available. The RecallAgent will function with limited capabilities.")
                await self.send_message("Note: Running with limited capabilities (no tools available).")

            # Initialize conversation with system message and user query
            messages = [
                {
                    "role": "system",
                    "content": f"""You are {self.name}, {self.description}
Your role is to {self.role} with the goal to {self.goal}
You have access to specialized tools that can help you answer queries.

WHEN TO USE TOOLS:
1. ALWAYS check conversation history using get_conversation_history when:
   - The query contains pronouns (he, she, it, they, etc.)
   - The query references something mentioned earlier
   - The query is a follow-up to a previous question
   - The query is incomplete or requires context to understand

2. Use solve_math_problem for any calculations, equations, or numerical problems.

3. Use get_user_facts when:
   - The query is about the user's preferences, history, or personal information
   - For personalized recommendations based on user data

4. Use search_user_files when:
   - The query refers to documents or files
   - The user wants information from specific content they've uploaded

For general knowledge questions with no references to previous context, you can answer directly without tools.
NEVER make up information. If you don't know or can't use tools to find the answer, say so honestly.
Keep your final answers concise and directly focused on the user's query."""
                },
                {
                    "role": "user", 
                    "content": f"User ID: {user_id}\nQuery: {query}"
                }
            ]
            
            # Main conversation loop for tool calling
            max_tool_calls = 5  # Prevent infinite loops
            tool_call_count = 0
            final_response = None
            
            while tool_call_count < max_tool_calls:
                # Call the LLM with the current conversation
                await self.send_message("Thinking it through...")
                response_data = await self.call_llm_with_tools(messages)
                
                # Extract the response message
                try:
                    response_message = response_data.get("message", {})
                    message_content = response_message.get("content", "")
                    tool_calls = response_message.get("tool_calls", [])
                    
                    # Add the message to our conversation
                    messages.append({
                        "role": "assistant",
                        "content": message_content,
                        "tool_calls": tool_calls if tool_calls else None
                    })
                    
                    # If no tool calls, we have our final answer
                    if not tool_calls:
                        final_response = message_content
                        break
                    
                    # Process tool calls
                    for tool_call in tool_calls:
                        tool_call_count += 1
                        
                        # Execute the tool
                        tool_call_id = tool_call.get("id", "")
                        tool_name = tool_call.get("function", {}).get("name", "unknown")
                        
                        result = await self.execute_tool_call(tool_call)
                        
                        # Add tool result to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(result)
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing LLM response: {e}")
                    break
            
            # If we didn't get a final response (e.g., hit max tool calls), get one
            if not final_response:
                # Ask for final answer with all tool results
                messages.append({
                    "role": "user", 
                    "content": "Based on the information gathered, please provide your final answer to my original query."
                })
                
                response_data = await self.call_llm_with_tools(messages)
                final_response = response_data.get("message", {}).get("content", "")
            
            # Remove any <think>...</think> sections from the response
            if final_response:
                import re
                final_response = re.sub(r'<think>.*?</think>', '', final_response, flags=re.DOTALL).strip()
            
            # Send completion message
            await self.send_message("Recall Agent has found an answer")
            
            # Return the formatted response
            return self.format_response(final_response)
            
        except Exception as e:
            logger.error(f"Error in Recall agent: {e}")
            import traceback
            traceback.print_exc()
            return self.format_response("I encountered an error while processing your query. Please try again.")
    
    def answer_query(self, query: str, user_id: str, message_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Synchronous wrapper for answer_query_async. This method should be used when called from a non-async context.
        It creates a new event loop if needed to run the async method.
        
        Args:
            query: Query to answer
            user_id: User ID making the query
            message_callback: Optional callback function to send messages (must be async-compatible)
            
        Returns:
            Dictionary containing the formatted response
        """
        # Create message callback wrapper that works in both sync and async contexts
        async def async_callback_wrapper(message):
            if message_callback:
                if asyncio.iscoroutinefunction(message_callback):
                    await message_callback(message)
                else:
                    # Call sync function directly
                    message_callback(message)
        
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new loop for this call to avoid conflicts
                new_loop = asyncio.new_event_loop()
                result = new_loop.run_until_complete(
                    self.answer_query_async(query, user_id, async_callback_wrapper)
                )
                new_loop.close()
                return result
            else:
                # Use existing loop
                return loop.run_until_complete(
                    self.answer_query_async(query, user_id, async_callback_wrapper)
                )
        except RuntimeError:
            # No event loop exists, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.answer_query_async(query, user_id, async_callback_wrapper)
            )
            loop.close()
            return result
    
    def format_response(self, answer: str, response_score: Optional[float] = None, is_math_tool_query: bool = False, context_document: Optional[str] = None) -> Dict[str, Any]:
        """Format the response in the standard format expected by the frontend.
        
        Args:
            answer: The answer text
            response_score: Optional score for the response quality
            is_math_tool_query: Whether this was a math query
            context_document: Optional name of document used for context
            
        Returns:
            Dictionary containing the formatted response
        """
        
        formatted_response = {
            "answer": answer,
            "agent_name": "recall"
        }
        
        # Add optional fields if provided
        if response_score is not None:
            formatted_response["response_score"] = response_score
            
        if is_math_tool_query:
            formatted_response["is_math_tool_query"] = is_math_tool_query
            
        if context_document:
            formatted_response["context_document"] = context_document
            
        return formatted_response
    
    def __del__(self):
        """Clean up MCP client connection when the agent is destroyed."""
        try:
            if hasattr(self, 'mcp_client'):
                self.mcp_client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting MCP client: {e}")
            pass 