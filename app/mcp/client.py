#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MCP (Model Context Protocol) client for Move37.
This client provides an interface for interacting with the MCP server.
"""

import asyncio
import logging
import json
import re
from typing import List, Dict, Any, Optional, Union
from fastmcp import Client
from fastmcp.client.transports import SSETransport

from app.core.config import MCP_SERVER_HOST, MCP_SERVER_PORT

logger = logging.getLogger(__name__)

class MCPClient:
    """A client for interacting with the MCP server."""
    
    def __init__(self, url: Optional[str] = None):
        """
        Initialize the MCP client.
        
        Args:
            url: Optional URL for the MCP server. If not provided, the default URL will be used.
        """
        self._client_url = url or f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse"
        transport = SSETransport(self._client_url)
        self._client = Client(transport)
        
        # Cache for available tools
        self._cached_tools = None
        self._last_tools_fetch = None
        self._tools_cache_ttl = 3600  # Time to live for cached tools in seconds (1 hour)
        
        # Cache for available resources
        self._cached_resources = None
        self._last_resources_fetch = None
        self._resources_cache_ttl = 3600  # Time to live for cached resources in seconds (1 hour)
    
    async def get_available_tools(self) -> List[Any]:
        """
        Get available tools from MCP server, using cache if available.
        
        Returns:
            List of available tools
        """
        current_time = asyncio.get_event_loop().time()
        
        # Check if cache is valid
        if (self._cached_tools is not None and 
            self._last_tools_fetch is not None and 
            current_time - self._last_tools_fetch < self._tools_cache_ttl):
            return self._cached_tools
            
        # Cache is invalid or doesn't exist, fetch tools
        try:
            async with self._client:
                tools = await self._client.list_tools()
                self._cached_tools = tools
                self._last_tools_fetch = current_time
                return tools
        except Exception as e:
            logger.error(f"Error listing tools: {str(e)}")
            # If we have cached tools and encounter an error, use the cache as fallback
            if self._cached_tools is not None:
                logger.warning("Using cached tools as fallback after fetch error")
                return self._cached_tools
            raise  # Re-raise if we have no cached tools
    
    async def get_available_resources(self, user_id: str = "default_user") -> List[Any]:
        """
        Get available resources from MCP server for a given user ID.
        Since FastMCP doesn't expose resources in list_resources(), we return the known resource URIs.
        
        Args:
            user_id: User ID to use for resource URIs. Defaults to "default_user".
            
        Returns:
            List of resource objects with URIs for the given user
        """
        current_time = asyncio.get_event_loop().time()
        
        # Check if cache is valid
        if (self._cached_resources is not None and 
            self._last_resources_fetch is not None and 
            current_time - self._last_resources_fetch < self._resources_cache_ttl):
            return self._cached_resources
            
        # Cache is invalid or doesn't exist, create resource objects
        try:
            # First try to get any resources from the server
            async with self._client:
                server_resources = await self._client.list_resources()
            
            # Define our known resources as dictionaries
            known_resources = [
                {
                    "name": "Recent Conversation History",
                    "description": "Provides the past 2 days of conversation history for a user",
                    "uri": f"conversations://{user_id}/recent-history"
                },
                {
                    "name": "User Preferences",
                    "description": "User's preferences and settings",
                    "uri": f"user://{user_id}/preferences"
                }
            ]
            
            resource_objects = known_resources.copy()
            # Add any server resources that aren't in our known list
            if server_resources:
                for server_resource in server_resources:
                    if not any(r["uri"] == getattr(server_resource, "uri", None) for r in resource_objects):
                        # Convert server_resource to dict if needed
                        if isinstance(server_resource, dict):
                            resource_objects.append(server_resource)
                        else:
                            resource_objects.append({
                                "name": getattr(server_resource, "name", "Unknown Resource"),
                                "description": getattr(server_resource, "description", "No description available"),
                                "uri": getattr(server_resource, "uri", "")
                            })
            self._cached_resources = resource_objects
            self._last_resources_fetch = current_time
            return resource_objects
            
        except Exception as e:
            logger.error(f"Error creating resource URIs: {str(e)}")
            # If we have cached resources and encounter an error, use the cache as fallback
            if self._cached_resources is not None:
                logger.warning("Using cached resources as fallback after error")
                return self._cached_resources
            raise  # Re-raise if we have no cached resources
    
    async def refresh_tools_cache(self) -> bool:
        """
        Force refresh the tools cache.
        
        Returns:
            True if refresh succeeded, False otherwise
        """
        try:
            tools = await self._client.list_tools()
            self._cached_tools = tools
            self._last_tools_fetch = asyncio.get_event_loop().time()
            return True
        except Exception as e:
            logger.error(f"Error refreshing tools cache: {str(e)}")
            
            # Try to reconnect and try again
            try:
                tools = await self._client.list_tools()
                self._cached_tools = tools
                self._last_tools_fetch = asyncio.get_event_loop().time()
                return True
            except Exception as reconnect_error:
                logger.error(f"Reconnection attempt for cache refresh failed: {reconnect_error}")
                return False
    
    async def refresh_resources_cache(self) -> bool:
        """
        Force refresh the resources cache.
        
        Returns:
            True if refresh succeeded, False otherwise
        """
        try:
            resources = await self._client.list_resources()
            self._cached_resources = resources
            self._last_resources_fetch = asyncio.get_event_loop().time()
            return True
        except Exception as e:
            logger.error(f"Error refreshing resources cache: {str(e)}")
            
            # Try to reconnect and try again
            try:
                resources = await self._client.list_resources()
                self._cached_resources = resources
                self._last_resources_fetch = asyncio.get_event_loop().time()
                return True
            except Exception as reconnect_error:
                logger.error(f"Reconnection attempt for cache refresh failed: {reconnect_error}")
                return False
    
    async def refresh_all_caches(self) -> bool:
        """
        Force refresh both tools and resources caches.
        
        Returns:
            True if both refreshes succeeded, False otherwise
        """
        tools_success = await self.refresh_tools_cache()
        resources_success = await self.refresh_resources_cache()
        
        return tools_success and resources_success
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        Call a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to call
            params: Parameters to pass to the tool
            
        Returns:
            Result of the tool call
        """
        try:
            async with self._client:
                result = await self._client.call_tool(tool_name, params)
                return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise
    
    async def read_resource(self, uri: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Read a resource from the MCP server.
        
        Args:
            uri: Resource URI to read
            params: Optional parameters for the resource
            
        Returns:
            Resource data
        """
        try:
            async with self._client:
                resource = await self._client.read_resource(uri, params or {})
                return resource
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {str(e)}")
            raise
    
    def format_tools_for_prompt(self, tools: List[Any]) -> str:
        """
        Format the tools list for inclusion in a prompt.
        
        Args:
            tools: List of tool objects from MCP.
            
        Returns:
            Formatted string describing the tools.
        """
        tool_descriptions = []
        
        for tool in tools:
            # Extract tool information based on FastMCP 2.0 format
            tool_name = getattr(tool, 'name', 'unknown')
            description = getattr(tool, 'description', 'No description provided')
            
            # Handle inputSchema instead of parameter_schema
            input_schema = getattr(tool, 'inputSchema', {})
            properties = {}
            required = []
            
            if input_schema:
                properties = input_schema.get('properties', {})
                required = input_schema.get('required', [])
            
            # Format parameters
            param_desc = []
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                param_description = param_info.get('description', '')
                param_requirement = "required" if param_name in required else "optional"
                param_desc.append(f"  - {param_name} ({param_type}, {param_requirement}): {param_description}")
            
            param_str = "\n".join(param_desc) if param_desc else "  No parameters required"
            
            tool_descriptions.append(f"Tool: {tool_name}\nDescription: {description}\nParameters:\n{param_str}")
        
        return "\n\n".join(tool_descriptions)
    
    def prepare_tool_params(self, tool: Any, params: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Prepare parameters for a tool call.
        
        Args:
            tool: The tool object.
            params: The original parameters.
            user_id: The user ID to include if needed.
            
        Returns:
            Dictionary of prepared parameters.
        """
        # Create a copy of parameters to avoid modifying the original
        tool_params = dict(params)
        
        try:
            # Extract input schema information
            input_schema = getattr(tool, 'inputSchema', {}) or {}
            properties = input_schema.get('properties', {})
            
            # Check if user_id is needed for this tool based on schema
            if "user_id" in properties and ("user_id" not in tool_params or not tool_params.get("user_id")):
                tool_params["user_id"] = user_id
            
            return tool_params
            
        except Exception as e:
            logger.error(f"Error preparing tool parameters: {e}")
            # Just return the original parameters if we encounter an error
            return tool_params
            
    def extract_tool_result(self, result: Any) -> Any:
        """
        Extract the result from a tool call response in a generalized way.
        
        Args:
            result: The raw result from a tool call.
            
        Returns:
            Extracted and formatted result
        """
        try:
            # If result is None, return empty string
            if result is None:
                return ""
                
            # Handle different response formats from FastMCP 2.0
            if hasattr(result, 'content') and result.content:
                # Case 1: Content is a list of objects with text attributes
                if isinstance(result.content, list):
                    # Join all text content if possible
                    text_content = []
                    for item in result.content:
                        if hasattr(item, 'text'):
                            text_content.append(item.text)
                        elif isinstance(item, dict) and "text" in item:
                            text_content.append(item["text"])
                        elif isinstance(item, str):
                            text_content.append(item)
                    if text_content:
                        return " ".join(text_content)
                
                # Case 2: Content is a single object with text attribute
                if hasattr(result.content, 'text'):
                    return result.content.text
            
            # Case 3: Direct text attribute
            if hasattr(result, 'text'):
                return result.text
                
            # Case 4: Value attribute
            if hasattr(result, 'value'):
                return result.value
            
            # Case 5: Result is a dictionary
            if isinstance(result, dict):
                # Look for common result keys
                for key in ["result", "answer", "response", "content", "data", "text", "output"]:
                    if key in result:
                        return result[key]
                # Return the whole dict if no common keys found
                return result
                
            # Case 6: Result is a string
            if isinstance(result, str):
                return result
                
            # Case 7: Result is a list
            if isinstance(result, list):
                # Try to convert list items to strings and join them
                try:
                    return " ".join(str(item) for item in result)
                except Exception:
                    return result
            
            # Case 8: JSON convertible object
            if hasattr(result, 'json') and callable(result.json):
                try:
                    return result.json()
                except Exception:
                    pass
            
            # Case 9: Dictionary-like object
            if hasattr(result, '__dict__'):
                return result.__dict__
            
            # Case 10: Any other object - convert to string
            return str(result)
            
        except Exception as e:
            logger.error(f"Error extracting tool result: {e}")
            return {"error": f"Failed to parse tool result: {str(e)}"}
    
    def extract_resource_content(self, resource_response: Any) -> str:
        """
        Extract content from a resource response in a generalized way.
        
        Args:
            resource_response: The response from a resource fetch
            
        Returns:
            Extracted content as a string
        """
        if not resource_response:
            return ""
            
        try:
            # Extract content from response based on common patterns
            if hasattr(resource_response, 'content'):
                # Handle list of content items
                if isinstance(resource_response.content, list) and len(resource_response.content) > 0:
                    # Check if content items have text attribute
                    if hasattr(resource_response.content[0], 'text'):
                        return resource_response.content[0].text
                    # Try direct string access if items are strings
                    elif isinstance(resource_response.content[0], str):
                        return resource_response.content[0]
                    # Try to join content if it's a list of objects
                    else:
                        try:
                            return "\n".join(str(item) for item in resource_response.content)
                        except Exception:
                            pass
                            
                # Handle content object with text attribute
                elif hasattr(resource_response.content, 'text'):
                    return resource_response.content.text
                # Handle content that is a direct string
                elif isinstance(resource_response.content, str):
                    return resource_response.content
                    
            # Try direct text attribute
            if hasattr(resource_response, 'text'):
                return resource_response.text
                
            # Try value attribute
            if hasattr(resource_response, 'value'):
                return str(resource_response.value)
                
            # Try dictionary access
            if isinstance(resource_response, dict):
                # Look for common content keys
                for key in ["content", "text", "data", "value", "result", "response"]:
                    if key in resource_response:
                        content = resource_response[key]
                        return content if isinstance(content, str) else str(content)
                        
            # Last resort: convert to string
            return str(resource_response)
            
        except Exception as e:
            logger.error(f"Error extracting resource content: {e}")
            return f"Error extracting resource content: {e}"
    
    def extract_resource_usages(self, text: str) -> Dict[str, Dict[str, str]]:
        """
        Extract resource usage requests from LLM output.
        This is the legacy method that parses complex resource objects.
        
        Args:
            text: Raw text from LLM output
            
        Returns:
            Dictionary mapping resource IDs to resource info dictionaries.
        """
        try:
            # Look for resource access patterns in the text
            resource_matches = re.findall(r'(?:```json\s*\n)?\s*{\s*"action"\s*:\s*"read_resource"\s*,\s*"resource_uri"\s*:\s*"([^"]+)"\s*(?:,\s*"reasoning"\s*:\s*"([^"]+)")?\s*}(?:\s*\n\s*```)?', text, re.DOTALL)
            
            resource_usages = {}
            for idx, match in enumerate(resource_matches):
                resource_uri = match[0].strip()
                reasoning = match[1].strip() if len(match) > 1 and match[1] else "No reasoning provided"
                
                # Generate a unique ID for this resource
                resource_id = f"resource_{idx + 1}"
                
                # Extract a name from the URI if possible
                uri_parts = resource_uri.split('/')
                resource_name = uri_parts[-1] if len(uri_parts) > 1 else resource_uri
                
                resource_usages[resource_id] = {
                    "resource_uri": resource_uri,
                    "name": resource_name,
                    "reasoning": reasoning
                }
                
            return resource_usages
            
        except Exception as e:
            logger.error(f"Error extracting resource usages: {str(e)}")
            return {}
            
    def extract_resource_uris(self, text: str) -> List[str]:
        """
        Extract resource URIs from LLM output.
        This simplified method just returns a list of URIs to fetch.
        
        Args:
            text: Raw text from LLM output
            
        Returns:
            List of resource URIs to fetch.
        """
        try:
            # Look for resource access patterns in the text
            resource_matches = re.findall(r'(?:```json\s*\n)?\s*{\s*"action"\s*:\s*"read_resource"\s*,\s*"resource_uri"\s*:\s*"([^"]+)"\s*(?:,\s*"reasoning"\s*:\s*"([^"]+)")?\s*}(?:\s*\n\s*```)?', text, re.DOTALL)
            
            resource_uris = []
            for match in resource_matches:
                resource_uri = match[0].strip()
                if resource_uri and resource_uri not in resource_uris:
                    resource_uris.append(resource_uri)
                
            return resource_uris
            
        except Exception as e:
            logger.error(f"Error extracting resource URIs: {str(e)}")
            return []
    
    def format_resources_for_prompt(self, resources: List[Any]) -> str:
        """
        Format a list of resources into a human-readable string for inclusion in a prompt.
        
        Args:
            resources: List of resource objects to format
            
        Returns:
            Formatted string describing the resources
        """
        if not resources:
            return "No resources available."
            
        descriptions = []
        for resource in resources:
            name = getattr(resource, 'name', 'Unknown Resource')
            description = getattr(resource, 'description', 'No description available')
            uri = getattr(resource, 'uri', 'No URI available')
            
            formatted_desc = f"- {name}: {description} (URI: {uri})"
            descriptions.append(formatted_desc)
            
        return "\n".join(descriptions)
    
    def extract_tool_calls(self, llm_response: str, tools: List[Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from the LLM response.
        
        Args:
            llm_response: The response from the LLM.
            tools: List of available tools.
            
        Returns:
            List of tool calls with their parameters.
        """
        # If no tools available, return empty list
        tool_names = [tool.name for tool in tools]
        if not tool_names:
            logger.warning("No tools available for extraction")
            return []
            
        # Create a tool name lookup for schema information
        tool_lookup = {tool.name: tool for tool in tools}
        
        # Check thinking section for explicit "no tool needed" decisions
        if "<think>" in llm_response and "</think>" in llm_response:
            thinking_match = re.search(r'<think>(.*?)</think>', llm_response, re.DOTALL)
            if thinking_match:
                thinking = thinking_match.group(1).lower()
                no_tool_phrases = [
                    "don't need a tool", "doesn't require a tool", "no need for a tool",
                    "no tool necessary", "can answer directly", "directly without tools",
                    "i don't need tools", "should answer directly"
                ]
                if any(phrase in thinking for phrase in no_tool_phrases):
                    logger.info("LLM explicitly decided not to use tools")
                    return []
        
        tool_calls = []
        
        # Try to find structured JSON format first
        json_patterns = [
            r'```json\s*({.*?"name"\s*:\s*"[^"]*".*?})\s*```',  # JSON in code blocks
            r'({.*?"name"\s*:\s*"[^"]*".*?})'                  # Raw JSON
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, llm_response, re.DOTALL)
            for match in matches:
                try:
                    call_data = json.loads(match)
                    tool_name = call_data.get("name")
                    
                    # Skip if tool name is invalid
                    if tool_name not in tool_names:
                        logger.warning(f"Ignoring call to unknown tool: {tool_name}")
                        continue
                        
                    params = call_data.get("params", {})
                    tool_calls.append({"name": tool_name, "params": params})
                except json.JSONDecodeError:
                    continue
        
        # If we found JSON-formatted calls, return them
        if tool_calls:
            return tool_calls
        
        # Fallback to function-call format: tool_name(param1=value1, param2=value2)
        for tool_name in tool_names:
            # Find function-call style pattern
            pattern = rf'{re.escape(tool_name)}\s*\(([^)]*)\)'
            matches = re.findall(pattern, llm_response, re.DOTALL)
            
            for param_text in matches:
                # Parse parameters
                params = {}
                param_pairs = re.findall(r'(["\']?[\w_]+["\']?)\s*[=:]\s*(["\'][^"\']*["\']|[^,}\)\s]+)', param_text)
                
                for key, val in param_pairs:
                    clean_key = key.strip('\'"')
                    clean_val = val.strip('\'"')
                    
                    # Try to convert types when appropriate
                    if clean_val.isdigit():
                        params[clean_key] = int(clean_val)
                    elif clean_val.lower() in ['true', 'false']:
                        params[clean_key] = clean_val.lower() == 'true'
                    else:
                        params[clean_key] = clean_val
                
                # Add the tool call
                tool_calls.append({"name": tool_name, "params": params})
        
        return tool_calls
        
    def detect_tool_mentions(self, llm_response: str, tools: List[Any]) -> List[str]:
        """
        Detect mentions of tools in the LLM response, even when not properly formatted as tool calls.
        
        Args:
            llm_response: The response from the LLM.
            tools: List of available tools.
            
        Returns:
            List of tool names that are mentioned in the response.
        """
        if not llm_response or not tools:
            return []
            
        tool_names = [tool.name for tool in tools]
        mentioned_tools = []
        
        # Common phrases that indicate tool usage intent
        intent_phrases = [
            "use the", "using the", "call the", "calling the", 
            "need to use", "should use", "could use", "would use",
            "tool:", "function:", "with the tool", "using tool"
        ]
        
        # Check each tool name for mentions with intent phrases
        for tool_name in tool_names:
            # Direct mention (case insensitive)
            if re.search(rf'\b{re.escape(tool_name)}\b', llm_response, re.IGNORECASE):
                # Check if there's an intent phrase near the tool mention
                for phrase in intent_phrases:
                    # Look for intent phrase within 10 words of tool name
                    pattern = rf'({re.escape(phrase)}\s+\w+(?:\s+\w+){{0,10}}\s+{re.escape(tool_name)})|({re.escape(tool_name)}\s+\w+(?:\s+\w+){{0,10}}\s+{re.escape(phrase)})'
                    if re.search(pattern, llm_response, re.IGNORECASE):
                        mentioned_tools.append(tool_name)
                        break
                
                # If no intent phrase found, check for direct "toolName:" pattern
                if tool_name not in mentioned_tools and re.search(rf'{re.escape(tool_name)}\s*:', llm_response, re.IGNORECASE):
                    mentioned_tools.append(tool_name)
                    
        return mentioned_tools 