#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Thinker agent for the Move 37 application.
This agent leverages the MCP protocol to use tools for answering queries.
"""

import json
import logging
import requests
import re
import inspect
import asyncio
from typing import Dict, Any, Optional, Callable, List, Union
from fastmcp import Client
from pydantic import BaseModel

from app.core.config import (
    THINKER_LLM_PROVIDER,
    THINKER_LLM_MODEL,
    FAST_PROCESSING_LLM_MODEL,
    CHAT_API_URL,
    MCP_SERVER_HOST,
    MCP_SERVER_PORT
)

logger = logging.getLogger(__name__)

class ThinkerAgent:
    """
    ThinkerAgent is a Model Context Protocol (MCP) based agent that 
    can leverage various tools to answer user queries.
    """
    
    def __init__(self):
        """Initialize the Thinker agent."""
        self.name = "Thinker"
        self.description = "I'm a Thinker agent that can use tools to answer your questions."
        self.role = "Assistant"
        self.goal = "To assist users by leveraging specialized tools."
        self.llm_provider = THINKER_LLM_PROVIDER
        self.llm_model = THINKER_LLM_MODEL
        self.message_callback = None
        self._cached_tools = None  # Cache for available tools
        self._last_tools_fetch = None  # Timestamp of last tools fetch
        self._tools_cache_ttl = 3600  # Time to live for cached tools in seconds (1 hour)
        
        # Conversation context tracking
        self._recent_exchanges = []  # List of [query, answer] pairs
        self._max_recent_exchanges = 3  # Keep last 3 exchanges in memory
        self._context_entities = None  # Cache for extracted context entities
        
        # Client instance - initialized once but used with context manager each time
        self._client_url = f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/sse"
        self._client = Client(self._client_url)
        
        # Shared context handling instructions used across different prompts
        self._context_handling_instructions = """
IMPORTANT: When a user's question contains pronouns (he, she, it, they) or references previous information:
1. FIRST look at the most recent conversation history to resolve these references
2. Use conversation history to understand CONTEXT, not just to find answers
3. If a follow-up question relates to information you just provided, use that information
"""
    
    def _add_to_conversation_context(self, query: str, answer: str):
        """
        Add a new exchange to the recent conversation context.
        
        Args:
            query: The user's query
            answer: The agent's answer
        """
        self._recent_exchanges.append({"query": query, "answer": answer})
        
        # Keep only the most recent exchanges
        if len(self._recent_exchanges) > self._max_recent_exchanges:
            self._recent_exchanges.pop(0)  # Remove oldest exchange
            
        # Reset context entities as they need to be re-analyzed
        self._context_entities = None
            
        logger.info(f"Updated conversation context. Now tracking {len(self._recent_exchanges)} recent exchanges.")

    # Make alias for compatibility with other agents
    async def answer_query_async(self, query: str, user_id: str, message_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Async wrapper for answer_query. This is here for compatibility with the conductor_agent.
        """
        return await self.answer_query(query, user_id, message_callback)
    
    async def answer_query(self, query: str, user_id: str, message_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Answer a user query using MCP tools.
        
        Args:
            query: The user's query.
            user_id: The ID of the user making the query.
            message_callback: Optional callback function for status messages.
            
        Returns:
            Dictionary with the answer and related metadata.
        """
        # Set the message callback if provided
        if message_callback:
            self.message_callback = message_callback
        
        
        try:
            # Use the FastMCP client with proper context manager pattern
            async with self._client:
                # Get available tools using cache when possible
                self._send_status_message("Thinker is getting available tools...")
                try:
                    tools = await self._get_available_tools()
                except Exception as e:
                    logger.error(f"Error listing tools: {str(e)}")
                    return self._format_error_response(
                        f"I encountered an error while connecting to my tools: {str(e)}",
                        "There was an error connecting to the tools needed to answer your query."
                    )
                
                # Extract context entities to enhance the system prompt
                context_entities = await self._extract_context_entities()
                
                # Log extraction status
                if context_entities is False:
                    logger.warning("Context extraction failed, proceeding without context")
                elif not context_entities:
                    logger.info("No context entities extracted (empty string)")
                else:
                    logger.info(f"Successfully extracted context: {context_entities[:50]}...")
                
                # Generate prompts based on available tools and context
                system_prompt = await self._create_system_prompt(tools, user_id, context_entities)
                
                # Create a simple user prompt without conversation history
                user_prompt = f"\n\nUser ID: {user_id}\nCurrent Query: {query}\n\nPlease answer this query."
                
                # Analyze query with LLM to determine tools needed
                self._send_status_message("Thinker is analyzing your query...")
                try:
                    llm_response = self._call_llm(system_prompt=system_prompt, user_prompt=user_prompt)
                    clean_llm_response = self._clean_response(llm_response)
                    tool_calls = self._extract_tool_calls(llm_response, tools)
                    
                    # Check if the response indicates a need for any resources
                    resources_to_fetch = self._extract_resource_usages(llm_response)
                    
                except Exception as e:
                    logger.error(f"Error processing LLM response: {str(e)}")
                    return self._format_error_response(
                        f"I encountered an error while processing your query: {str(e)}",
                        "There was an error analyzing your query."
                    )
                
                # Fetch any requested resources
                fetched_resources = {}
                if resources_to_fetch:
                    for resource_id, resource_info in resources_to_fetch.items():
                        try:
                            resource_uri = resource_info.get("resource_uri")
                            resource_name = resource_info.get("name", resource_id)
                            
                            self._send_status_message(f"Fetching {resource_name}...")
                            resource_response = await self._client.read_resource(resource_uri)
                            
                            # Extract content from the resource response in a generic way
                            resource_content = self._extract_resource_content(resource_response)
                            
                            if resource_content:
                                fetched_resources[resource_id] = {
                                    "name": resource_name,
                                    "content": resource_content,
                                    "uri": resource_uri
                                }
                                logger.info(f"Successfully fetched resource: {resource_name}")
                            
                        except Exception as e:
                            logger.error(f"Error fetching resource {resource_name}: {str(e)}")
                            # Continue without this resource
                
                # If we have fetched resources, incorporate them into a new prompt and re-analyze
                if fetched_resources:
                    context_sections = []
                    for resource_id, resource_data in fetched_resources.items():
                        resource_content = resource_data["content"]
                        resource_name = resource_data["name"]
                        context_sections.append(f"INFORMATION FROM RESOURCE {resource_name.upper()}:\n\n{resource_content}")
                    
                    # Create an enhanced prompt with all resource context
                    context_prompt = f"\n\nUser ID: {user_id}\n\n" + "\n\n".join(context_sections) + f"\n\nCurrent Query: {query}\n\nPlease answer this query."
                    
                    self._send_status_message("Analyzing query with additional context...")
                    llm_response = self._call_llm(system_prompt=system_prompt, user_prompt=context_prompt)
                    clean_llm_response = self._clean_response(llm_response)
                    # Re-extract tool calls with the updated response
                    tool_calls = self._extract_tool_calls(llm_response, tools)
                
                # If no tools are needed, return the direct response
                if not tool_calls:
                    response = {
                        "answer": clean_llm_response,
                        "reasoning": "I answered this query directly without using tools.",
                        "agent_name": self.name
                    }
                    # Update conversation context with this exchange
                    self._add_to_conversation_context(query, clean_llm_response)
                    return response
                
                # Execute tool calls and collect results
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name")
                    params = tool_call.get("params", {})
                    
                    self._send_status_message(f"Thinker is using {tool_name}...")
                    
                    try:
                        # Get the tool and prepare parameters
                        tool_obj = next((t for t in tools if t.name == tool_name), None)
                        if not tool_obj:
                            logger.warning(f"Skipping invalid tool name: {tool_name}")
                            continue
                        
                        # Prepare and call the tool
                        tool_params = self._prepare_tool_params(tool_obj, params, user_id)
                        logger.info(f"Calling tool {tool_name} with params: {tool_params}")
                        
                        # Use FastMCP's call_tool method within the context
                        result = await self._client.call_tool(tool_name, tool_params)
                        
                        tool_results.append({
                            "tool_name": tool_name,
                            "result": self._extract_tool_result(result)
                        })
                    except Exception as e:
                        logger.error(f"Error calling tool {tool_name}: {e}")
                        tool_results.append({
                            "tool_name": tool_name,
                            "error": str(e)
                        })
                
                # Format the final response with tool results
                try:
                    response = await self._format_final_response(query, llm_response, tool_results)
                    # Update conversation context with this exchange
                    self._add_to_conversation_context(query, response["answer"])
                    return response
                except Exception as e:
                    logger.error(f"Error formatting final response: {str(e)}")
                    
                    # Fallback response when formatting fails
                    results_text = "\n".join([
                        f"Tool {r['tool_name']} returned: {r.get('result', r.get('error', 'Unknown'))}" 
                        for r in tool_results
                    ])
                    
                    response = {
                        "answer": f"Here are the results of my tools: {results_text}",
                        "reasoning": "I used tools to find information, but had trouble formulating a complete answer.",
                        "agent_name": self.name,
                        "error": str(e)
                    }
                    # Update conversation context even with fallback response
                    self._add_to_conversation_context(query, response["answer"])
                    return response
                
        except Exception as e:
            logger.error(f"Error in ThinkerAgent: {str(e)}")
            return self._format_error_response(
                f"I encountered an error while processing your query: {str(e)}",
                "There was an error connecting to the tools needed to answer your query."
            )
    
    def _format_error_response(self, answer: str, reasoning: str) -> Dict[str, Any]:
        """Helper to create consistent error responses."""
        return {
            "answer": answer,
            "reasoning": reasoning,
            "agent_name": self.name,
            "error": answer
        }
    
    def _extract_tool_result(self, result: Any) -> Any:
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
    
    def _format_tools_for_prompt(self, tools: List[Any]) -> str:
        """
        Format the tools list for inclusion in the prompt.
        
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
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call the LLM with the given prompts.
        
        Args:
            system_prompt: System instructions for the LLM.
            user_prompt: User message to process.
            
        Returns:
            LLM response text.
        """
        try:
            # Using Ollama API with the Thinker's LLM configuration
            url = CHAT_API_URL
            
            # Prepare the payload
            payload = {
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.2}  # Lower temperature for more deterministic responses
            }

            print(f"----------\nPayload: {payload}\n----------")
            
            # Make the API call
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            # Extract the content from the response
            response_json = response.json()
            
            # Try different response formats based on the API response structure
            if "message" in response_json and "content" in response_json["message"]:
                return response_json["message"]["content"]
            elif "response" in response_json:
                return response_json["response"]
            else:
                raise ValueError("Unexpected response format from LLM API")
                
        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            raise

    def _extract_tool_calls(self, llm_response: str, tools: List[Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from the LLM response.
        
        Args:
            llm_response: The response from the LLM.
            tools: List of available tools.
            
        Returns:
            List of tool calls with their parameters.
        """
        logger.info("Extracting tool calls from LLM response...")
        
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
                    logger.info(f"Extracted tool call to {tool_name} from JSON")
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
                logger.info(f"Extracted tool call to {tool_name} from function-style format")
        
        return tool_calls
        
    def _parse_parameters_from_text(self, param_text: str, tool_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Parse parameters from text with enhanced extraction and validation.
        
        Args:
            param_text: Text containing parameters.
            tool_schema: Optional schema information for the tool.
            
        Returns:
            Dictionary of parameter names and values.
        """
        params = {}
        
        # Log the raw parameter text for debugging
        logger.debug(f"Raw parameter text: {param_text}")
        
        # Extract key-value pairs using regex
        # This pattern handles quotes better and captures more formats
        param_pairs = re.findall(r'(["\']?[\w_]+["\']?)\s*[=:]\s*(["\'][^"\']*["\']|[^,}\)\s]+)', param_text)
        
        # Process each pair
        for key, val in param_pairs:
            # Clean up the key and value
            clean_key = key.strip('\'"')
            clean_val = val.strip('\'"')
            
            logger.debug(f"Extracted parameter: {clean_key}={clean_val}")
            
            # Try to convert numbers and booleans if appropriate
            if clean_val.isdigit():
                params[clean_key] = int(clean_val)
            elif clean_val.lower() in ['true', 'false']:
                params[clean_key] = clean_val.lower() == 'true'
            else:
                params[clean_key] = clean_val
        
        # If we have a schema, do validation and type conversion
        if tool_schema and 'properties' in tool_schema:
            properties = tool_schema.get('properties', {})
            
            # Check for expected parameter types
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                
                # If param exists, validate/convert its type
                if param_name in params:
                    value = params[param_name]
                    
                    # Convert to appropriate type based on schema
                    if param_type == 'integer' and isinstance(value, str):
                        try:
                            params[param_name] = int(value)
                        except ValueError:
                            logger.warning(f"Could not convert {param_name}='{value}' to integer")
                    elif param_type == 'boolean' and isinstance(value, str):
                        if value.lower() in ['true', 'yes', '1']:
                            params[param_name] = True
                        elif value.lower() in ['false', 'no', '0']:
                            params[param_name] = False
        
        # Log the final parsed parameters
        logger.info(f"Final parsed parameters: {params}")
        return params

    async def _format_final_response(self, query: str, llm_response: str, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format the final response using the LLM response and tool results.
        
        Args:
            query: The original user query.
            llm_response: The response from the LLM.
            tool_results: Results from any tool calls.
            
        Returns:
            Formatted response dictionary.
        """
        # If we have tool results, we need to format a final answer using them
        if tool_results:
            self._send_status_message("Thinker is formulating final answer...")
            
            # Prepare a prompt for the LLM to interpret tool results
            system_prompt = f"""You are the Thinker agent (also referred to as "Agent Thinker"), tasked with providing a clear, concise answer based on tool results.
Given the original user query and results from tools, provide a complete and helpful answer.
Your response should be clear, factual, and directly address the user's question.

{self._context_handling_instructions}
"""
            
            # Format the tool results for the LLM
            tool_results_str = json.dumps(tool_results, indent=2)
            
            user_prompt = f"""Original query: {query}

Tool results:
{tool_results_str}

Based on these results, provide a clear, helpful answer to the original query.
"""
            
            try:
                # Get the final answer from the LLM
                final_answer = self._call_llm(system_prompt, user_prompt)
                
                # Clean the thinking from the final answer
                cleaned_answer = self._clean_response(final_answer)
                
                return {
                    "answer": cleaned_answer,
                    "reasoning": "I used specialized tools to find this answer.",
                    "agent_name": self.name,
                    "tool_results": tool_results
                }
                
            except Exception as e:
                logger.error(f"Error formulating final answer: {str(e)}")
                # Use a simplified answer if the LLM call fails
                results_text = "\n".join([f"Tool {r['tool_name']} returned: {r.get('result', '')}" for r in tool_results])
                return {
                    "answer": f"Here are the results of my tools: {results_text}",
                    "reasoning": "I used tools to find information, but had trouble formulating a complete answer.",
                    "agent_name": self.name,
                    "error": str(e)
                }
        else:
            # If no tools were used, just return the cleaned LLM response directly
            cleaned_response = self._clean_response(llm_response)
            return {
                "answer": cleaned_response,
                "reasoning": "I answered this query directly without using tools.",
                "agent_name": self.name
            }
    
    

    def _prepare_tool_params(self, tool: Any, params: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Prepare parameters for a tool call in a generalized way.
        
        Args:
            tool: The tool object.
            params: The original parameters from the LLM.
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
            required_params = input_schema.get('required', [])
            
            logger.info(f"Initial parameters for {tool.name}: {tool_params}")
            
            # Check if user_id is needed for this tool based on schema
            if "user_id" in properties and ("user_id" not in tool_params or not tool_params.get("user_id")):
                tool_params["user_id"] = user_id
                logger.info(f"Added user_id={user_id} to parameters for {tool.name} based on schema")
            
            # Clean string parameters to remove any thinking tags
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                
                if param_name in tool_params and param_type == 'string' and isinstance(tool_params[param_name], str):
                    tool_params[param_name] = self._clean_response(tool_params[param_name])
            
            logger.info(f"Final parameters for {tool.name}: {tool_params}")
            return tool_params
            
        except Exception as e:
            logger.error(f"Error preparing tool parameters: {e}")
            # Just return the original parameters if we encounter an error
            return tool_params
            
    async def _create_system_prompt(self, tools: List[Any], user_id: str, context_entities: Union[str, bool] = "") -> str:
        """
        Create a dynamic system prompt based on available tools and conversation context.
        
        Args:
            tools: List of available tools.
            user_id: The user ID to include in the prompt.
            context_entities: Extracted context from previous conversations, or False if extraction failed.
            
        Returns:
            Formatted system prompt.
        """
        # Format the tool descriptions
        tool_descriptions = self._format_tools_for_prompt(tools)
        
        # Determine which tools require user_id
        tools_requiring_user_id = []
        for tool in tools:
            try:
                input_schema = getattr(tool, 'inputSchema', {}) or {}
                properties = input_schema.get('properties', {})
                if "user_id" in properties:
                    tools_requiring_user_id.append(tool.name)
            except Exception:
                pass

        # Build examples of how to use the tools
        # Generate examples of proper tool usage
        tool_examples_text = "HERE ARE SOME EXAMPLES OF HOW TO USE THE TOOLS:"
        for tool in tools:
            # Get tool details
            tool_name = tool.name
            input_schema = getattr(tool, 'inputSchema', {}) or {}
            properties = input_schema.get('properties', {})
            
            # Skip if no properties
            if not properties:
                continue
            
            # Build an example with parameters in correct order
            example_params = {}
            param_desc_parts = []
            
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                
                # Add user_id parameter with the actual value
                if param_name == 'user_id':
                    example_params[param_name] = user_id
                    param_desc_parts.append(f'{param_name}: "{user_id}"')
                # Add sample values for other parameters
                elif param_type == 'string':
                    sample_value = f"example_{param_name}"
                    example_params[param_name] = sample_value
                    param_desc_parts.append(f'{param_name}: "{sample_value}"')
                elif param_type == 'integer':
                    example_params[param_name] = 5
                    param_desc_parts.append(f'{param_name}: 5')
                elif param_type == 'boolean':
                    example_params[param_name] = True
                    param_desc_parts.append(f'{param_name}: true')
            
            # Format both JSON and function-call examples
            if param_desc_parts:
                # JSON format
                json_example = json.dumps({
                    "name": tool_name,
                    "params": example_params
                }, indent=2)
                
                # Function-call format
                func_example = f'{tool_name}({", ".join(param_desc_parts)})'
                
                # Add example as formatted text to the examples string
                tool_examples_text += f"\nExample for {tool_name}:\n```json\n{json_example}\n```\nOR as a function call: `{func_example}`\n"
        
        # Build the user_id guidance
        user_id_guidance = ""
        if tools_requiring_user_id:
            if len(tools_requiring_user_id) == len(tools):
                user_id_guidance = f"When using any tool, ALWAYS include the user_id parameter set to \"{user_id}\"."
            else:
                tool_list = ", ".join(tools_requiring_user_id)
                user_id_guidance = f"When using the following tools: {tool_list}, ALWAYS include the user_id parameter set to \"{user_id}\"."
        
        # Create information about available resources
        resource_information = f"""
AVAILABLE RESOURCES:

Resource: Conversation History
URI: conversations://{user_id}/recent-history
Description: Provides the past 2 days of conversation history for a user
When to use: When the user's query contains pronouns or references to previous conversations that need context to understand
Example usage:
```json
{{
  "action": "read_resource",
  "resource_uri": "conversations://{user_id}/recent-history",
  "reasoning": "Need conversation history to understand the context of the user's query"
}}
```

TO USE RESOURCES:
1. Identify when a resource would be helpful for understanding the query
2. Use client.read_resource() with the appropriate URI
3. Look at the resource's content before formulating your response
4. The answer you are looking for may not be in the resource, but it may still inform your response.
"""

        # Add context entities section if available
        context_section = ""
        if context_entities and context_entities is not False:
            # Print for debugging
            print(f"\n-------------------\nContext entities: {context_entities}\n-------------------\n")
            context_section = f"""HERE IS THE CONTEXT OF THE CONVERSATION SO FAR:
            
            {context_entities}

Use this context to better understand the user's query and provide more personalized response to the user's query.

"""
        
        # Create the complete prompt
        return f"""You are the Thinker agent, also known as "Agent Thinker". You are a specialized assistant that can use tools and resources to answer user queries to provide a helpful, accurate, and succinct answer.

You have access to the following tools but use them only when necessary:

{tool_descriptions}

{resource_information}

INSTRUCTIONS FOR ANSWERING USER QUERIES:

1. If the user's query can be answered using your own knowledge and without the use of tools, please do so. 
2. If the user's query is using pronouns ('he', 'she', 'it', 'they') or references information that is likely to be in the conversation history, you should use the conversation history resource to understand the subject and context.
3. There may be questions in the conversation history, but your task is only to answer the user's current query provided in the user prompt.
4. Don't ever make up information or make assumptions. If you don't know the answer, say so truthfully.
5. Since you are in a conversation with the user, refer to them as "you" or "your" when appropriate, or if you know their name, use it. But don't say "user" or "user_id" or anything like that to refer to them.
6. {user_id_guidance}


{tool_examples_text}


{context_section}

--------------------------------
"""
    
    async def _get_available_tools(self) -> List[Any]:
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
            logger.info("Using cached tools list")
            return self._cached_tools
            
        # Cache is invalid or doesn't exist, fetch tools
        try:
            logger.info("Fetching tools from MCP server")
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
    
    async def refresh_tools_cache(self):
        """
        Force refresh the tools cache.
        
        Returns:
            True if refresh succeeded, False otherwise
        """
        try:
            # Use the persistent client instead of creating a new one
            async with self._client:
                tools = await self._client.list_tools()
                self._cached_tools = tools
                self._last_tools_fetch = asyncio.get_event_loop().time()
                logger.info(f"Successfully refreshed tools cache. Found {len(tools)} tools.")
                return True
        except Exception as e:
            logger.error(f"Error refreshing tools cache: {str(e)}")
            
            # Try to reconnect and try again
            try:
                logger.info("Attempting to reconnect after cache refresh failure")
                async with self._client:
                    tools = await self._client.list_tools()
                    self._cached_tools = tools
                    self._last_tools_fetch = asyncio.get_event_loop().time()
                    logger.info(f"Successfully refreshed tools cache after reconnect. Found {len(tools)} tools.")
                    return True
            except Exception as reconnect_error:
                logger.error(f"Reconnection attempt for cache refresh failed: {reconnect_error}")
                return False
    
    def set_message_callback(self, callback: Callable):
        """
        Set a callback function for sending status messages.
        
        Args:
            callback: Function to call with status messages.
        """
        self.message_callback = callback

    def _send_status_message(self, message: str):
        """
        Send a status message via the callback if it's set.
        
        Args:
            message: Message to send.
        """
        if self.message_callback:
            try:
                # Check if the callback is a coroutine function (async)
                if inspect.iscoroutinefunction(self.message_callback):
                    # Create a task to run the coroutine
                    asyncio.create_task(self.message_callback(message))
                else:
                    # Call the sync function directly
                    self.message_callback(message)
            except Exception as e:
                logger.error(f"Error sending status message: {e}")
                # Continue execution even if sending the message fails
    
    def _clean_response(self, text: str) -> str:
        """
        Clean the LLM response by removing thinking tags and extra whitespace.
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
            
        try:
            # Remove <think>...</think> sections with case insensitivity
            cleaned = re.sub(r'(?i)<think>.*?</think>', '', text, flags=re.DOTALL)
            
            # Also handle cases where the thinking tags might be malformed or incomplete
            cleaned = re.sub(r'(?i)<think>.*?($|</)', '', cleaned, flags=re.DOTALL)
            cleaned = re.sub(r'(?i)(^|>).*?</think>', '', cleaned, flags=re.DOTALL)
            
            # Remove any remaining thinking tags that might be present
            cleaned = re.sub(r'(?i)</?think[^>]*>', '', cleaned)
            
            # Remove any leading/trailing whitespace
            cleaned = cleaned.strip()
            
            # If after cleaning, the result is empty, return the original with tags stripped
            if not cleaned:
                # Just strip any HTML-like tags as a fallback
                cleaned = re.sub(r'<[^>]+>', '', text)
                cleaned = cleaned.strip()
            
            return cleaned
        except Exception as e:
            logger.error(f"Error cleaning response: {e}")
            # Return original text with simple tag stripping as fallback
            return re.sub(r'<[^>]+>', '', text).strip()

    def _extract_resource_content(self, resource_response: Any) -> str:
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
            
    def _extract_resource_usages(self, llm_response: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract all resource usage instructions from the LLM response.
        
        Args:
            llm_response: The full LLM response text
            
        Returns:
            Dictionary mapping resource IDs to resource usage info
        """
        resource_usages = {}
        
        try:
            # Extract resource usages from JSON blocks
            json_pattern = r'```json\s*({.*?"action"\s*:\s*"read_resource".*?})\s*```'
            matches = re.findall(json_pattern, llm_response, re.DOTALL)
            
            for idx, match in enumerate(matches):
                try:
                    resource_data = json.loads(match)
                    # Check if this is a resource access request
                    if resource_data.get("action") == "read_resource" and "resource_uri" in resource_data:
                        resource_id = resource_data.get("id", f"resource_{idx}")
                        resource_name = resource_data.get("name", "Resource")
                        resource_uri = resource_data.get("resource_uri")
                        
                        resource_usages[resource_id] = {
                            "resource_uri": resource_uri,
                            "name": resource_name,
                            "reasoning": resource_data.get("reasoning", "")
                        }
                except json.JSONDecodeError:
                    continue
                    
            # If no JSON blocks found, try simpler pattern matching
            if not resource_usages:
                # Look for common resource URI schemes
                uri_patterns = [
                    (r'conversations://[^\s"\']+', "Conversation History"),
                    (r'documents://[^\s"\']+', "Document"),
                    (r'data://[^\s"\']+', "Data"),
                    (r'files://[^\s"\']+', "File")
                ]
                
                for idx, (pattern, name) in enumerate(uri_patterns):
                    uris = re.findall(pattern, llm_response)
                    for uri_idx, uri in enumerate(uris):
                        resource_id = f"resource_{idx}_{uri_idx}"
                        resource_usages[resource_id] = {
                            "resource_uri": uri,
                            "name": name,
                            "reasoning": "Extracted from text pattern"
                        }
                        
            return resource_usages
            
        except Exception as e:
            logger.error(f"Error extracting resource usages: {e}")
            return {}

    async def _extract_context_entities(self) -> Union[str, bool]:
        """
        Extract important entities and context from recent conversations using a fast LLM.
        
        Returns:
            String containing the key entities and context, or False if extraction failed
        """
        # If no recent exchanges, return empty context
        if not self._recent_exchanges:
            logger.info("No recent exchanges found, skipping context extraction")
            return ""
            
        # If we already have extracted entities and they're still valid, return them
        if self._context_entities is not None:
            logger.info("Using cached context entities")
            return self._context_entities
            
        # Format conversations for analysis
        conversation_text = ""
        for i, exchange in enumerate(self._recent_exchanges, 1):
            conversation_text += f"Exchange {i}:\n"
            conversation_text += f"User: {exchange['query']}\n"
            conversation_text += f"Assistant: {exchange['answer']}\n\n"
        
        # Create a prompt for entity extraction
        prompt = f"""
Please analyze these recent conversation exchanges and identify:
1. The main subjects/topics being discussed
2. Key entities (people, places, things, dates, concepts) that may be mentioned
3. Any important context that would help if follow-up questions are asked
4. User preferences or constraints if mentioned

Format your response as a very concise summary paragraph with about 3 sentences, that captures the essential context. Do not include a title. 

Recent conversation:
{conversation_text}
"""
        
        # Try up to 2 times (initial attempt + 1 retry)
        for attempt in range(2):
            try:
                if attempt > 0:
                    logger.warning(f"Retrying context extraction (attempt {attempt+1}/2)")
                
                logger.info(f"Extracting context entities using {FAST_PROCESSING_LLM_MODEL}")
                # Call the fast processing LLM
                url = CHAT_API_URL
                
                # Prepare the payload with the fast processing model
                payload = {
                    "model": FAST_PROCESSING_LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a helpful context analyzer. Extract only the most important context from conversations."},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1}  # Lower temperature for more consistent extraction
                }
                
                # Make the API call
                response = requests.post(url, json=payload, timeout=15)  # Increased timeout for reliability
                response.raise_for_status()
                
                # Extract the content from the response
                response_json = response.json()
                
                # Extract text based on API response format
                entity_text = None
                if "message" in response_json and "content" in response_json["message"]:
                    entity_text = response_json["message"]["content"]
                elif "response" in response_json:
                    entity_text = response_json["response"]
                
                # Validate we got a meaningful response
                if not entity_text or len(entity_text.strip()) < 10:
                    logger.warning(f"Received suspiciously short or empty context: '{entity_text}'")
                    if attempt == 0:
                        continue  # Try again
                    else:
                        return False  # Give up after second attempt
                
                # Cache the extracted entities
                self._context_entities = entity_text
                logger.info(f"Successfully extracted context entities: {entity_text[:100]}...")
                return entity_text
                    
            except Exception as e:
                logger.error(f"Error extracting context entities (attempt {attempt+1}/2): {str(e)}")
                if attempt == 0:
                    # Wait a moment before retry
                    await asyncio.sleep(1)
                    continue
                else:
                    # Final attempt failed
                    return False
        
        # This should never be reached due to the return in the loop, but just in case
        return False