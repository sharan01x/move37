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
            
        logger.info(f"Updated conversation context. Now tracking {len(self._recent_exchanges)} recent exchanges.")

    def _format_conversation_context(self) -> str:
        """
        Format the recent conversation exchanges for inclusion in prompts.
        
        Returns:
            Formatted string of recent exchanges
        """
        if not self._recent_exchanges:
            return "No recent conversation history available."
            
        context = "RECENT CONVERSATION CONTEXT:\n\n"
        
        for i, exchange in enumerate(self._recent_exchanges, 1):
            context += f"Exchange {i}:\n"
            context += f"User: {exchange['query']}\n"
            context += f"You (Thinker): {exchange['answer']}\n\n"
            
        # Add explicit reference resolution hints if possible
        if self._recent_exchanges:
            latest = self._recent_exchanges[-1]
            # Extract potential entities from the last answer that might be referenced
            entities = self._extract_potential_entities(latest['answer'])
            if entities:
                context += "REFERENCE RESOLUTION HINTS:\n"
                for entity in entities:
                    context += f"- If the user refers to '{entity['pronoun']}', they are likely referring to '{entity['entity']}' mentioned in your last response.\n"
                context += "\n"
                
        return context
    
    def _extract_potential_entities(self, text: str) -> List[Dict[str, str]]:
        """
        Extract potential entities from text that might be referenced later with pronouns.
        Very simple implementation - in a real system, this would use NLP.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of entity objects with entity and potential pronoun
        """
        entities = []
        
        # Simple rules to find potential entities
        # Look for proper nouns (capitalized words not at the start of sentences)
        words = text.split()
        for i in range(1, len(words)):
            word = words[i].strip('.,;:!?()[]{}""\'')
            if word and word[0].isupper() and len(word) > 1 and not words[i-1].endswith('.'):
                # Determine likely pronoun based on common name endings or known entities
                pronoun = "it"  # Default
                
                # Very simple gender heuristic - would be much more sophisticated in production
                if word.lower() in ["he", "him", "his", "she", "her", "hers", "they", "them", "their"]:
                    continue  # Skip pronouns themselves
                    
                # Skip common non-entity capitalized words
                if word.lower() in ["i", "you", "we", "they", "the", "a", "an"]:
                    continue
                    
                entities.append({
                    "entity": word,
                    "pronoun": pronoun
                })
        
        # Ensure we're not sending too many entities back
        return entities[:3]  # Limit to top 3 potential entities

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
        
        self._send_status_message("Thinker is connecting to MCP server...")
        
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
                
                # Generate prompts based on available tools
                system_prompt = self._create_system_prompt(tools, user_id)
                
                # Include recent conversation context in the user prompt
                conversation_context = self._format_conversation_context()
                user_prompt = f"\n\nUser ID: {user_id}\n\n{conversation_context}\nCurrent Query: {query}\n\nPlease answer this query."
                
                # Analyze query with LLM to determine tools needed
                self._send_status_message("Thinker is analyzing your query...")
                try:
                    llm_response = self._call_llm(system_prompt=system_prompt, user_prompt=user_prompt)
                    clean_llm_response = self._clean_response(llm_response)
                    tool_calls = self._extract_tool_calls(llm_response, tools)
                except Exception as e:
                    logger.error(f"Error processing LLM response: {str(e)}")
                    return self._format_error_response(
                        f"I encountered an error while processing your query: {str(e)}",
                        "There was an error analyzing your query."
                    )
                
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
            
    def _create_system_prompt(self, tools: List[Any], user_id: str) -> str:
        """
        Create a dynamic system prompt based on available tools.
        
        Args:
            tools: List of available tools.
            user_id: The user ID to include in the prompt.
            
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
        tool_examples_text = ""
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
        
        # Create the complete prompt
        return f"""You are the Thinker agent, also known as "Agent Thinker". You are a specialized assistant that can use tools to answer user queries to provide a helpful, accurate, and succinct answer.

You have access to the following tools but use them only when necessary:

{tool_descriptions}

INSTRUCTIONS FOR ANSWERING USER QUERIES:

1. If the user's query can be answered using your own knowledge and without the use of tools, please do so. 
2. If the user's query is using pronouns ('he', 'she', 'it', 'they') or references information that is likely to be in the conversation history, get the conversation history to understand the subject and context. 
3. There may be questions in the conversation history, but your tasks is only to answer the user's current query provided in the user prompt.
4. Don't ever make up information or make assumptions. If you don't know the answer, say so truthfully.
5. Since you are in a conversation with the user, refer to them as "you" or "your" when appropriate, or if you know their name, use it. But don't say "user" or "user_id" or anything like that to refer to them.
6. {user_id_guidance}

HERE ARE SOME EXAMPLES OF HOW TO USE THE TOOLS:

{tool_examples_text}

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