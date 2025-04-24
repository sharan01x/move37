#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Base agent class for the LifeScribe application.
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum

from langchain_community.tools import Tool
from langchain_core.tools import BaseTool
from crewai import Agent, Task


from app.core.config import (
    OPENAI_API_KEY,
    CONDUCTOR_LLM_PROVIDER, CONDUCTOR_LLM_MODEL,
    TRANSCRIBER_LLM_PROVIDER, TRANSCRIBER_LLM_MODEL,
    RECORDER_LLM_PROVIDER, RECORDER_LLM_MODEL,
    FIRST_RESPONDER_LLM_PROVIDER, FIRST_RESPONDER_LLM_MODEL,
    NUMBER_NINJA_LLM_PROVIDER, NUMBER_NINJA_LLM_MODEL,
    PERSEPHONE_LLM_PROVIDER, PERSEPHONE_LLM_MODEL,
    BUTTERFLY_LLM_PROVIDER, BUTTERFLY_LLM_MODEL,
    CHAT_API_URL
)


class BaseAgent:
    """Base agent class for the LifeScribe application."""
    
    def __init__(self, name: str, description: str, role: str, goal: str, tools: List[BaseTool] = None, llm_provider: str = None, llm_model: str = None):
        """
        Initialize the base agent.
        
        Args:
            name: Name of the agent.
            description: Description of the agent.
            role: Role of the agent.
            goal: Goal of the agent.
            tools: Tools available to the agent.
            llm_provider: LLM provider to use.
            llm_model: LLM model to use.
        """
        self.name = name
        self.description = description
        self.role = role
        self.goal = goal
        self.tools = tools or []
        self.llm_provider = llm_provider or CONDUCTOR_LLM_PROVIDER or TRANSCRIBER_LLM_PROVIDER or RECORDER_LLM_PROVIDER or FIRST_RESPONDER_LLM_PROVIDER or NUMBER_NINJA_LLM_PROVIDER or PERSEPHONE_LLM_PROVIDER or BUTTERFLY_LLM_PROVIDER or "ollama"
        self.llm_model = llm_model or CONDUCTOR_LLM_MODEL or TRANSCRIBER_LLM_MODEL or RECORDER_LLM_MODEL or FIRST_RESPONDER_LLM_MODEL or NUMBER_NINJA_LLM_MODEL or PERSEPHONE_LLM_MODEL or BUTTERFLY_LLM_MODEL or "qwen2.5:latest"
        
        # Message callback (will be set by methods that need to send messages)
        self.message_callback = None

        # Create the CrewAI agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> Agent:
        """
        Create a CrewAI agent.
        
        Returns:
            CrewAI agent.
        """
        # Configure the LLM based on the provider
        if self.llm_provider == "openai" and OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=self.llm_model,
                temperature=0.7,
                openai_api_key=OPENAI_API_KEY
            )
        else:  # Default to Ollama
            # For crewai 0.102.0, use direct string for local Ollama models
            llm = f"{self.llm_provider}/{self.llm_model}"  # Format is 'provider/model'
        
        # Create the agent
        agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.description,
            verbose=True,
            allow_delegation=False,
            tools=self.tools,
            llm=llm
        )
        
        return agent
    
    def get_llm(self):
        return self.agent.llm
    
    async def send_message(self, message: str):
        """
        Send a message to the frontend if a message callback is set.
        
        Args:
            message: Message to send.
        """
        if self.message_callback:
            print(f"{self.name} agent sending message: {message}")
            await self.message_callback(message)
            
    def set_message_callback(self, callback: Callable[[str], None]):
        """
        Set the message callback function.
        
        Args:
            callback: Function to call with messages.
        """
        self.message_callback = callback

    def format_response(self, answer: str, response_score: Optional[float] = None, is_math_tool_query: bool = False) -> Dict[str, Any]:
        """
        Format a response in the standard format expected by the frontend.
        
        Args:
            answer: The answer text from the agent.
            response_score: Optional score for the response.
            is_math_tool_query: Whether this is a math tool query.
            
        Returns:
            Dictionary containing the formatted response.
        """
        return {
            "answer": answer,
            "agent_name": self.name.lower().replace(" ", "_"),
            "display_name": self.name,
            "response_score": response_score,
            "is_math_tool_query": is_math_tool_query
        }

    async def queryLLM(
        self, 
        user_prompt: str, 
        model: str = None, 
        system_prompt: str = None, 
        stream: bool = False, 
        temperature: float = 0.0
    ) -> str:
        """
        Query the LLM with given prompts.
        
        Args:
            user_prompt: The user prompt to send to the LLM
            model: The model to use (defaults to the agent's model if not specified)
            system_prompt: Optional system prompt to send before the user prompt
            stream: Whether to stream the response (default: False)
            temperature: Temperature setting for response generation (default: 0.0)
            
        Returns:
            The text response from the LLM
            
        Raises:
            ValueError: If the LLM returns an empty response
            requests.RequestException: If the API call fails
            Exception: For any other errors during processing
        """
        # Use the specified model or default to the agent's model
        model_to_use = model or self.llm_model
        
        # Prepare the messages array
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        
        # Prepare the payload for the API
        payload = {
            "model": model_to_use,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": temperature}
        }
        
        # Make the API call
        response = requests.post(CHAT_API_URL, json=payload)
        response.raise_for_status()  # Raise exception for non-200 responses
        
        # Parse the response
        response_json = response.json()
        content = response_json.get("message", {}).get("content", "")
        
        # If content is empty, try alternative formats (for different API implementations)
        if not content:
            content = response_json.get("response", "")
        
        if not content:
            raise ValueError("Empty response from LLM API")
            
        return content
