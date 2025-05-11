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
from pydantic import BaseModel

from app.core.config import (
    THINKER_LLM_PROVIDER,
    THINKER_LLM_MODEL,
    FAST_PROCESSING_LLM_MODEL,
    CHAT_API_URL
)
from app.mcp.client import MCPClient
from app.tools.user_information_tool import get_user_preferences, get_user_facts_relevant_to_query

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
        
        # Conversation context tracking
        self._recent_exchanges = []  # List of [query, answer] pairs
        self._max_recent_exchanges = 3  # Keep last 3 exchanges in memory
        self._context_entities = None  # Cache for extracted context entities
        
        # Initialize the MCP client
        self._mcp_client = MCPClient()
        
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
            # Get available tools and resources
            self._send_status_message("Thinker is evaluating the available tools and resources...")
            try:
                tools = await self._mcp_client.get_available_tools()
                resources = await self._mcp_client.get_available_resources()
            except Exception as e:
                logger.error(f"Error listing tools: {str(e)}")
                return self._format_error_response(
                    f"I encountered an error while getting my tools and resources: {str(e)}",
                    "There was an error connecting to the server."
                )

            # Extract context entities to enhance the system prompt
            context_entities = await self._extract_context_entities()
            
            # Log extraction status
            if context_entities is False:
                logger.warning("Context extraction failed, proceeding without context")
            elif not context_entities:
                pass  # No context entities extracted (empty string)
            
            # Generate prompts based on available tools and context
            system_prompt = await self._create_system_prompt(tools, user_id, query, context_entities, resources)
            
            # Create a simple user prompt without conversation history
            user_prompt = f"\n\nUser ID: {user_id}\nCurrent Query: {query}\n\nPlease answer this query."
            
            # Analyze query with LLM to determine tools needed
            self._send_status_message("Thinker is analyzing your query...")
            try:
                llm_response = self._call_llm(system_prompt=system_prompt, user_prompt=user_prompt)
                clean_llm_response = self._clean_response(llm_response)
                tool_calls = self._mcp_client.extract_tool_calls(llm_response, tools)
                resource_uris_to_fetch = self._mcp_client.extract_resource_uris(llm_response)
                
            except Exception as e:
                logger.error(f"Error processing LLM response: {str(e)}")
                return self._format_error_response(
                    f"I encountered an error while processing your query: {str(e)}",
                    "There was an error analyzing your query."
                )
            
            # Fetch any requested resources
            fetched_resources = {}
            if resource_uris_to_fetch:
                for resource_uri in resource_uris_to_fetch:
                    try:
                        # Find the resource name based on the URI
                        resource_name = "Resource"
                        if resources:
                            for resource in resources:
                                # Handle both dictionary and object formats for resources
                                if isinstance(resource, dict):
                                    resource_uri_template = resource.get('uri', '')
                                    if resource_uri_template and '{user_id}' in resource_uri_template:
                                        matched_uri = resource_uri_template.replace('{user_id}', user_id)
                                        if matched_uri == resource_uri:
                                            resource_name = resource.get('name', 'Resource')
                                            break
                                else:
                                    # Fallback to getattr for objects
                                    resource_uri_template = getattr(resource, 'uri', '')
                                    # Replace user_id placeholder for matching
                                    if '{user_id}' in resource_uri_template:
                                        matched_uri = resource_uri_template.replace('{user_id}', user_id)
                                        if matched_uri == resource_uri:
                                            resource_name = getattr(resource, 'name', 'Resource')
                                            break
                        
                        self._send_status_message(f"Fetching {resource_name}...")
                        resource_response = await self._mcp_client.read_resource(resource_uri)
                        
                        # Extract content from the resource response in a generic way
                        resource_content = self._mcp_client.extract_resource_content(resource_response)
                        
                        if resource_content:
                            resource_id = f"resource_{len(fetched_resources) + 1}"
                            fetched_resources[resource_id] = {
                                "name": resource_name,
                                "content": resource_content,
                                "uri": resource_uri
                            }
                        
                    except Exception as e:
                        logger.error(f"Error fetching resource {resource_uri}: {str(e)}")
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
                tool_calls = self._mcp_client.extract_tool_calls(llm_response, tools)
            
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
                    tool_params = self._mcp_client.prepare_tool_params(tool_obj, params, user_id)
                    
                    # Call the tool via MCPClient
                    result = await self._mcp_client.call_tool(tool_name, tool_params)
                    
                    tool_results.append({
                        "tool_name": tool_name,
                        "result": self._mcp_client.extract_tool_result(result)
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
    
    async def _create_system_prompt(self, tools: List[Any], user_id: str, query: str, context_entities: Union[str, bool] = "", resources: List[Any] = None) -> str:
        """
        Create a dynamic system prompt based on available tools and conversation context.
        
        Args:
            tools: List of available tools.
            user_id: The user ID to include in the prompt.
            context_entities: Extracted context from previous conversations, or False if extraction failed.
            resources: List of available resources from the server.
            
        Returns:
            Formatted system prompt.
        """
        # Format the tool descriptions
        tool_descriptions = self._mcp_client.format_tools_for_prompt(tools)
        
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
        
        # Build the user preferences block
        user_preference_information = "USER PREFERENCES:\n\n"
        try:
            user_preference_information += get_user_preferences(user_id)
        except Exception as e:
            logger.error(f"Error fetching user preferences: {e}")
            user_preference_information = ""

        # Build the set of user facts that are relevant to the user's query
        user_facts = "FACTS ABOUT THE USER RELEVANT TO THE QUERY:\n\n"
        try:
            user_facts += get_user_facts_relevant_to_query(user_id, query)
        except Exception as e:
            logger.error(f"Error fetching user facts: {e}")
            user_facts = ""
        
        # Build the user_id guidance
        user_id_guidance = ""
        if tools_requiring_user_id:
            if len(tools_requiring_user_id) == len(tools):
                user_id_guidance = f"When using any tool, ALWAYS include the user_id parameter set to \"{user_id}\"."
            else:
                tool_list = ", ".join(tools_requiring_user_id)
                user_id_guidance = f"When using the following tools: {tool_list}, ALWAYS include the user_id parameter set to \"{user_id}\"."
        
        # Create information about available resources
        resource_information = ""
        
        # Use dynamically fetched resources if available
        if resources and len(resources) > 0:
            resource_information += "AVAILABLE RESOURCES:\n\n"
            for resource in resources:
                # Handle both dictionary and object formats for resources
                if isinstance(resource, dict):
                    resource_name = resource.get('name', 'Unknown Resource')
                    resource_description = resource.get('description', 'No description available')
                    resource_uri = resource.get('uri', '')
                else:
                    # Fallback to getattr for objects
                    resource_name = getattr(resource, 'name', 'Unknown Resource')
                    resource_description = getattr(resource, 'description', 'No description available')
                    resource_uri = getattr(resource, 'uri', '')
                
                # Skip if no URI is available
                if not resource_uri:
                    continue
                    
                # Replace user_id placeholder if present
                if '{user_id}' in resource_uri:
                    resource_uri = resource_uri.replace('{user_id}', user_id)
                
                resource_information += f"Resource: {resource_name}\n"
                resource_information += f"URI: {resource_uri}\n"
                resource_information += f"Description: {resource_description}\n"
                resource_information += f"When to use: When you need {resource_description.lower()}\n"
                resource_information += f"Example usage:\n"
                resource_information += f"```json\n"
                resource_information += f"{{\n"
                resource_information += f"  \"action\": \"read_resource\",\n"
                resource_information += f"  \"resource_uri\": \"{resource_uri}\",\n"
                resource_information += f"  \"reasoning\": \"Need {resource_name.lower()} to better understand or answer the query\"\n"
                resource_information += f"}}\n"
                resource_information += f"```\n\n"

        resource_information += """
TO USE RESOURCES:
1. Identify when a resource would be helpful for understanding the query
2. Use client.read_resource() with the appropriate URI
3. Look at the resource's content before formulating your response
4. The answer you are looking for may not be in the resource, but it may still inform your response.
"""

        # Add context entities section if available
        context_section = ""
        if context_entities and context_entities is not False:
            context_section = f"""HERE IS THE CONTEXT OF THE CONVERSATION SO FAR:
            
{context_entities}

"""
        
        # Create the complete prompt
        system_prompt = f"""You are the Thinker agent, also known as "Agent Thinker". You are a specialized assistant that can use tools and resources to answer user queries to provide a helpful, accurate, and succinct answer.

You have access to the following tools and resources but use them only when necessary:

{tool_descriptions}

{tool_examples_text}

{resource_information}

{user_id_guidance}

{user_preference_information}

{user_facts}

INSTRUCTIONS FOR ANSWERING USER QUERIES:

1. If the user's query can be answered using your own knowledge and without the use of tools, please do so. 
2. If the user's query is using pronouns ('he', 'she', 'it', 'they') or references information that is likely to be in the conversation history, you should use the conversation history resource to understand the subject and context.
3. If you need to reference something from the past conversations, try to find it first through the conversation history resource before using any other tools to find the information. It's just faster.
3. There may be questions in the conversation history, but your task is only to answer the user's current query provided in the user prompt.
4. Don't ever make up information or make assumptions. If you don't know the answer, say so truthfully.
5. Since you are in a conversation with the user, refer to them as "you" or "your" when appropriate, or if you know their name, use it. But don't say "user" or "user_id" or anything like that to refer to them.
6. If you have the user's preferences or facts about the user, use them to personalize the answer to the user's query in a friendly and engaging way.
7. If you are provided the context of the conversation so far, use it to better understand the user's query and provide a more personalized answer. 

{context_section}
--------------------------------
"""

        # Print the prompt for debugging
        print(f"Generated system prompt:\n\n{system_prompt}\n\n")

        return system_prompt
    
    async def _extract_context_entities(self) -> Union[str, bool]:
        """
        Extract important entities and context from recent conversations using a fast LLM.
        
        Returns:
            String containing the key entities and context, or False if extraction failed
        """
        # If no recent exchanges, return empty context
        if not self._recent_exchanges:
            return ""
            
        # If we already have extracted entities and they're still valid, return them
        if self._context_entities is not None:
            return self._context_entities
            
        # Format conversations for analysis
        conversation_text = ""
        for i, exchange in enumerate(self._recent_exchanges, 1):
            conversation_text += f"Exchange {i}:\n"
            conversation_text += f"User: {exchange['query']}\n"
            conversation_text += f"Assistant: {exchange['answer']}\n\n"

        # Do the LLM analysis only if there are any recent exchanges
        if conversation_text:
            # Create a prompt for entity extraction
            prompt = f"""
Please analyze these recent conversation exchanges and identify:
1. The main subjects/topics being discussed
2. Key entities (people, places, things, dates, concepts) that may be mentioned
3. Any important context that would help if follow-up questions are asked

Format your response as a very concise summary paragraph with about 3 sentences, that captures the essential context. Do not include a title. 

Recent conversation:
{conversation_text}
"""
        
        # Try up to 2 times (initial attempt + 1 retry)
        for attempt in range(2):
            try:
                if attempt > 0:
                    logger.warning(f"Retrying context extraction (attempt {attempt+1}/2)")
                
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
        else:
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