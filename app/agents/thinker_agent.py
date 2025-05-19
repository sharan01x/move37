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
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List, Union
from pydantic import BaseModel

from app.core.config import (
    THINKER_LLM_PROVIDER,
    THINKER_LLM_MODEL,
    FAST_PROCESSING_LLM_MODEL,
    CHAT_API_URL,
    USER_LOCATION,
    USER_LANGUAGE
)
from app.mcp.client import MCPClient
from app.tools.user_information_tool import get_user_preferences, get_user_facts_relevant_to_query, get_user_goals
from app.database.conversation_db import ConversationDBInterface
from app.agents.user_fact_extractor_agent import UserFactExtractorAgent
from app.models.messages import MessageType

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
        
        # Initialize User Fact Extractor Agent
        self.user_fact_extractor_agent = UserFactExtractorAgent()
    
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
            self._send_status_message("Evaluating the available tools and resources...")
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
            self._send_status_message("Analyzing your query...")
            
            # Track whether we have already tried to refine the response
            refinement_attempts = 0
            max_refinement_attempts = 4
            
            while refinement_attempts <= max_refinement_attempts:
                self._send_status_message(f"Let me refine the response and try again ({refinement_attempts}/{max_refinement_attempts})...")
                try:
                    # Get response from LLM
                    llm_response = self._call_llm(system_prompt=system_prompt, user_prompt=user_prompt)
                    clean_llm_response = self._clean_response(llm_response)
                    
                    # Extract proper tool calls
                    tool_calls = self._mcp_client.extract_tool_calls(llm_response, tools)
                    resource_uris_to_fetch = self._mcp_client.extract_resource_uris(llm_response)
                    
                    # If no structured tool calls found, check for tool mentions
                    if not tool_calls:
                        mentioned_tools = self._mcp_client.detect_tool_mentions(llm_response, tools)
                        
                        # If tools are mentioned but not properly called, refine the response
                        if mentioned_tools and refinement_attempts < max_refinement_attempts:
                            refinement_attempts += 1
                            self._send_status_message(f"Refining the approach (attempt {refinement_attempts})...")
                            
                            # Create a refinement prompt
                            tool_names_str = ", ".join([f"'{name}'" for name in mentioned_tools])
                            refinement_prompt = f"""You mentioned using the tool(s): {tool_names_str}, but didn't format the tool call correctly.

Please use the correct client.call_tool format. Here's the exact format for the tool(s) you mentioned:

"""
                            # Add format for each mentioned tool
                            for tool_name in mentioned_tools:
                                tool_obj = next((t for t in tools if t.name == tool_name), None)
                                if tool_obj:
                                    input_schema = getattr(tool_obj, 'inputSchema', {}) or {}
                                    properties = input_schema.get('properties', {})
                                    
                                    refinement_prompt += "```python\n"
                                    refinement_prompt += f'client.call_tool("{tool_name}", {{\n'
                                    
                                    # Add parameters with their descriptions
                                    for param_name, param_info in properties.items():
                                        param_type = param_info.get('type', 'string')
                                        param_description = param_info.get('description', '')
                                        
                                        # Format default value based on type
                                        if param_type == 'string':
                                            refinement_prompt += f'    "{param_name}": "value",  # {param_description}\n'
                                        elif param_type == 'integer':
                                            refinement_prompt += f'    "{param_name}": 0,  # {param_description}\n'
                                        elif param_type == 'number':
                                            refinement_prompt += f'    "{param_name}": 0.0,  # {param_description}\n'
                                        elif param_type == 'boolean':
                                            refinement_prompt += f'    "{param_name}": false,  # {param_description}\n'
                                        elif param_type == 'array':
                                            refinement_prompt += f'    "{param_name}": [],  # {param_description}\n'
                                        elif param_type == 'object':
                                            refinement_prompt += f'    "{param_name}": {{}},  # {param_description}\n'
                                        else:
                                            refinement_prompt += f'    "{param_name}": "value",  # {param_description}\n'
                                    
                                    refinement_prompt += "})\n```\n\n"

                            refinement_prompt += "Let me restate the query: {query}\n\nPlease provide a proper tool call to answer this query."
                            
                            print(f"\n[DEBUG] Refinement prompt:\n--------------------------------\n{refinement_prompt}")
                            
                            # Update the user prompt for refinement
                            user_prompt = refinement_prompt
                            continue  # Try again with the refinement prompt
                        # No tools mentioned or max refinements reached, proceed with direct response
                    
                    # Break out of the refinement loop if we have tool calls or max attempts reached
                    break
                    
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
                    context_sections.append(f"INFORMATION FROM RESOURCE {resource_name}:\n\n{resource_content}")

                # Add the new context to the system prompt
                system_prompt += "\n\n" + context_sections
                
                # Create an enhanced prompt with all resource context
                user_prompt = f"\n\nUser ID: {user_id}\n\nCurrent Query: {query}\n\nPlease answer this query."
                
                self._send_status_message("Analyzing query with additional context...")
                llm_response = self._call_llm(system_prompt=system_prompt, user_prompt=user_prompt)
                clean_llm_response = self._clean_response(llm_response)
                # Re-extract tool calls with the updated response
                tool_calls = self._mcp_client.extract_tool_calls(llm_response, tools)
            
            # If no tools are needed, return the direct response
            if not tool_calls:
                # Even after refinement, if there are still tool mentions but no proper calls,
                # add a warning to the response
                mentioned_tools = self._mcp_client.detect_tool_mentions(llm_response, tools)
                warning = ""
                if mentioned_tools:
                    tool_names = ", ".join(mentioned_tools)
                    warning = f"\n\nNote: I tried to use tools ({tool_names}) but encountered an issue with the tool call format. I've provided the best answer I can without using these tools."
                
                clean_response = clean_llm_response + warning if warning else clean_llm_response
                
                # Store conversation asynchronously
                asyncio.create_task(self._store_conversation_async(
                    user_id=user_id,
                    query=query,
                    direct_response=clean_response,
                    agent_name=self.name
                ))
                
                # Process conversation for user facts asynchronously
                asyncio.create_task(self.user_fact_extractor_agent.extract_facts(
                    f"User Query: {query}\nAgent Response: {clean_response}", 
                    user_id=user_id
                ))
                
                response = {
                    "answer": clean_response,
                    "reasoning": "I answered this query directly without using tools.",
                    "agent_name": self.name
                }
                # Update conversation context with this exchange
                self._add_to_conversation_context(query, response["answer"])
                return response
            
            # Execute tool calls and collect results
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                params = tool_call.get("params", {})
                
                self._send_status_message(f"Using {tool_name}...")
                
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
                response = await self._format_final_response(query, llm_response, tool_results, user_id)
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
            print(f"\n\nSystem prompt:\n--------------------------------\n{system_prompt}")
            print(f"\n\nUser prompt:\n--------------------------------\n{user_prompt}")

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

    async def _format_final_response(self, query: str, llm_response: str, tool_results: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """
        Format the final response using the LLM response and tool results.
        
        Args:
            query: The original user query.
            llm_response: The response from the LLM.
            tool_results: Results from any tool calls.
            user_id: The ID of the user making the query.
            
        Returns:
            Formatted response dictionary.
        """
        # If we have tool results, we need to format a final answer using them
        if tool_results:
            self._send_status_message("Formulating final answer...")

            # Format the tool results for the LLM
            tool_results_str = json.dumps(tool_results, indent=2)
            
            # Prepare a prompt for the LLM to interpret tool results
            system_prompt = f"""You are the Thinker Agent, also known as "Agent Thinker". You are providing a final, concise answer to a user's question based on tool results.

            Here are the results of the tool used prior to this:
            {tool_results_str}

            INSTRUCTIONS TO PERFORM YOUR TASK:
            1. Your response should be clear, factual, and directly address the question. 
            2. If there is information regarding the process that is necessary to find the final answer, you don't need to include it in your response.
            3. Be conversational and direct, starting with the answer itself
            4. If a follow-up question relates to information you just provided, use that information
            5. FIRST look at the most recent conversation history to resolve these references
            6. Use conversation history to understand CONTEXT, not just to find answers
            7. If the tool results are useful, use them to answer the question.
            8. Never make up information or make assumptions. If you don't know the answer, say so truthfully.
"""
            
            user_prompt = f"""Original query: {query}


Provide a clear, direct answer that addresses the query without mentioning the tools or process used.
"""
            
            try:
                # Get the final answer from the LLM
                final_answer = self._call_llm(system_prompt, user_prompt)
                
                # Clean the thinking from the final answer
                cleaned_answer = self._clean_response(final_answer)
                
                # Store conversation asynchronously after getting final answer
                asyncio.create_task(self._store_conversation_async(
                    user_id=user_id,
                    query=query,
                    direct_response=cleaned_answer,
                    agent_name=self.name
                ))

                # Process conversation for user facts asynchronously
                asyncio.create_task(self.user_fact_extractor_agent.extract_facts(
                    f"User Query: {query}\nAgent Response: {cleaned_answer}", 
                    user_id=user_id
                ))

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
            # Store conversation asynchronously for direct response
            asyncio.create_task(self._store_conversation_async(
                user_id=user_id,
                query=query,
                direct_response=cleaned_response,
                agent_name=self.name
            ))
            
            # Process conversation for user facts asynchronously
            asyncio.create_task(self.user_fact_extractor_agent.extract_facts(
                f"User Query: {query}\nAgent Response: {cleaned_response}", 
                user_id=user_id
            ))

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
        tool_information = "AVAILABLE TOOLS:\n\n"
        for tool in tools:
            # Get tool details
            tool_name = getattr(tool, 'name', 'unknown')
            description = getattr(tool, 'description', 'No description provided')
            parameters = getattr(tool, 'inputSchema', {}) or {}
            tool_information += f"Tool: {tool_name}\n"
            tool_information += f"Description: {description}\n"
            tool_information += "Example usage:\n"
            tool_information += f"```python\n"
            tool_information += f"client.call_tool(\"{tool_name}\", {{\n"
            for param, value in parameters.get('properties', {}).items():
                tool_information += f"  \"{param}\": \"{value}\",\n"
            tool_information += f"}})\n"
            tool_information += f"```\n\n"
        
        tool_information += """
TO USE TOOLS:
1. Identify when a tool would be helpful for understanding the query
2. Use client.call_tool() with the appropriate tool name and parameters
3. It is CRITICAL to follow the exact format of the tool call examples above when using any tool or else, the tool calls will fail.
"""

        # Use dynamically fetched resources if available
        resource_information = ""
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
                resource_information += f"```python\n"
                resource_information += f"client.read_resource(\"{resource_uri}\")\n"
                resource_information += f"```\n\n"

        resource_information += """
TO USE RESOURCES:
1. Identify when a resource would be helpful for understanding the query
2. Use client.read_resource() with the appropriate URI
3. It is CRITICAL to follow the exact format of the resource call examples above when using any resource or else, the resource calls will fail.
"""

        # Build the user preferences block
        user_preference_information = ""
        try:
            user_preference_information += get_user_preferences(user_id)
            if user_preference_information:
                user_preference_information = "\n\nUSER PREFERENCES:\n" + user_preference_information
        except Exception as e:
            logger.error(f"Error fetching user preferences: {e}")
            user_preference_information = ""

        # Build the set of user facts that are relevant to the user's query
        basic_information = "\n\nBASIC INFORMATION ABOUT THE USER:"
        basic_information += f"\n1. User's home location code is '{USER_LOCATION}'"
        basic_information += f"\n2. Time at home location is {datetime.now().strftime('%I:%M %p on %A, %B %d, %Y')}"
        basic_information += f"\n3. User's preferred language code is '{USER_LANGUAGE}'\n"

        user_facts = ""
        try:
            user_facts = get_user_facts_relevant_to_query(user_id, query)
            user_facts = "\n\nFACTS ABOUT THE USER RELEVANT TO THE QUERY:\n" + user_facts
        except Exception as e:
            logger.error(f"Error fetching user facts: {e}")
            user_facts = ""

        user_goals = ""
        try:
            user_goals = get_user_goals(user_id)
            if user_goals:
                user_goals = "\n\nLONG TERM GOALS OF THE USER:\n" + user_goals
        except Exception as e:
            logger.error(f"Error fetching user goals: {e}")
            user_goals = ""
        

        # Add context entities section if available
        context_section = ""
        if context_entities and context_entities is not False:
            context_section = f"""HERE IS THE CONTEXT OF THE CONVERSATION SO FAR:
            
{context_entities}

"""
        
        # Create the complete prompt
        system_prompt = f"""You are the Thinker agent, also known as "Agent Thinker". You are a specialized assistant that can use tools and resources to answer user queries to provide a helpful, accurate, and succinct answer.

You have access to the following tools and resources but use them only when necessary:

{tool_information}
{resource_information}
{basic_information}
{user_facts}
{user_preference_information}
{user_goals}
INSTRUCTIONS FOR ANSWERING USER QUERIES:

1. If the user's query can be answered using your own knowledge and without the use of tools, please do so. 
2. There may be questions in the conversation history, but your task is only to answer the user's current query provided in the user prompt.
3. Don't ever make up information or make assumptions. If you don't know the answer, say so truthfully.
4. Since you are in a conversation with the user, refer to them as "you" or "your" when appropriate, or if you know their name, use it. But don't say "user" or "user_id" or anything like that to refer to them.
5. If you have the user's preferences or facts about the user, use them to personalize the answer to the user's query in a friendly and engaging way.
6. If you are provided the context of the conversation so far, use it to better understand the user's query.
7. If you need to use a tool or resource but cannot execute it, just respond with the exact command you would use to execute it and you will be provided the results of that command.
8. If the user has long term goals, use them to better understand the user's query and see if you can be helpful to the user in achieving those goals.

{context_section}
--------------------------------
"""

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

    def _send_status_message(self, status_text: str):
        """
        Send a status message via the callback if it's set.
        
        Args:
            status_text: Message string to send.
        """
        if self.message_callback:
            message_payload = {
                "type": MessageType.STATUS_UPDATE,
                "data": {
                    "message": status_text,
                    "agent": self.name
                }
            }
            try:
                # Check if the callback is a coroutine function (async)
                if inspect.iscoroutinefunction(self.message_callback):
                    # Create a task to run the coroutine
                    asyncio.create_task(self.message_callback(message_payload))
                else:
                    # Call the sync function directly
                    self.message_callback(message_payload)
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

    # Update the conversation storage method to use asyncio
    async def _store_conversation_async(self, user_id: str, query: str, direct_response: str, agent_name: Optional[str] = None) -> None:
        """
        Store a conversation asynchronously using asyncio.
        
        Args:
            user_id: ID of the user.
            query: Original user query
            direct_response: Agent's response
            agent_name: Name of the agent that provided the response
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Create a user-specific conversation database to ensure we're storing in the right folder
            user_specific_db = ConversationDBInterface(user_id=user_id)
            
            # Store the conversation
            user_specific_db.add_conversation(
                user_id=user_id,
                user_query=query,
                agent_response=direct_response,
                agent_name=agent_name,
                timestamp=timestamp
            )
            
        except Exception as e:
            logger.error(f"Error in async conversation storage: {e}")