#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Number Ninja agent for the Move 37 application.
Specializes in answering mathematics-related questions.
"""

from typing import Dict, Any, Optional, Union, Callable
from crewai import Task
import re
import asyncio
from crewai.tools import BaseTool

from app.agents.base_agent import BaseAgent
from app.core.config import NUMBER_NINJA_LLM_PROVIDER, NUMBER_NINJA_LLM_MODEL
from app.utils.llm_utils import parse_json_response, extract_json_from_llm_response
from app.tools.math_tool import math_tool

# Create a properly wrapped math tool
class MathToolWrapper(BaseTool):
    name: str = "math_tool"
    description: str = "Solve mathematical problems"
    
    def _run(self, query: str) -> Dict[str, Any]:
        return math_tool.run(query)

class NumberNinjaAgent(BaseAgent):
    """
    Agent specialized in answering mathematics questions using an LLM.
    """
    
    def __init__(self):
        """Initialize the Number Ninja agent."""
        super().__init__(
            name="Number Ninja",
            description="I specialize in solving mathematical problems and equations.",
            role="Mathematics Expert",
            goal="Provide accurate solutions to mathematical problems and equations.",
            tools=[MathToolWrapper()], 
            llm_provider=NUMBER_NINJA_LLM_PROVIDER,
            llm_model=NUMBER_NINJA_LLM_MODEL
        )
    
    async def answer_query_async(self, query: str, user_id: str = None, message_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Answer a math query asynchronously.
        
        Args:
            query: The query to answer.
            user_id: The ID of the user making the query.
            message_callback: Optional callback function for sending messages.
            
        Returns:
            Dictionary containing the answer and whether it is a math tool query.
        """
        # Send initial status
        if message_callback:
            await message_callback(f"Number Ninja processing mathematical query...")
            
        # Check if it's a math query that can be handled with the math tool
        math_query_result = await self._process_math_query(query)
        
        # If it is a math tool query, return the result
        if math_query_result and math_query_result.get("is_math_tool_query"):
            response = math_query_result.get("answer", "I couldn't solve this math problem.")
            
            # Send the answer
            if message_callback:
                await message_callback(f"Number Ninja calculated result: {response}")
                
            return {
                "answer": response,
                "agent_name": "number_ninja",
                "display_name": "Number Ninja",
                "response_score": None,
                "is_math_tool_query": True
            }
        
        # If we get here, it's not a math tool query or the math tool couldn't solve it
        try:
            # Create a system prompt for more detailed math-focused instructions
            system_prompt = """
            You are Number Ninja, an expert mathematics agent. 
            You specialize in solving mathematical problems and providing clear, step-by-step solutions.
            You should:
            1. Properly identify the mathematical concepts involved in the question
            2. Show your work step-by-step when solving problems
            3. Double-check your calculations for accuracy
            4. Provide the final answer clearly
            5. Explain relevant mathematical concepts when appropriate
            
            If you cannot solve the problem or it's not a mathematical question, acknowledge your limitations.
            """
            
            # Get response from LLM with the specialized math prompt
            direct_response = await self.queryLLM(
                user_prompt=query,
                system_prompt=system_prompt
            )
            
            # Send the answer
            if message_callback:
                await message_callback(f"Number Ninja: {direct_response}")
                
            return {
                "answer": direct_response,
                "agent_name": "number_ninja",
                "display_name": "Number Ninja",
                "response_score": None,
                "is_math_tool_query": False  # Normal response, not a math tool query
            }
        except Exception as e:
            error_message = f"Error answering query: {str(e)}"
            print(error_message)
            
            if message_callback:
                await message_callback(f"Number Ninja Error: {error_message}")
                
            return {
                "answer": "I encountered an error while trying to solve your mathematical problem.",
                "agent_name": "number_ninja",
                "display_name": "Number Ninja",
                "response_score": None,
                "is_math_tool_query": False
            }
    
    async def _process_math_query(self, query: str) -> Dict[str, Any]:
        """
        Process a potential math query using the math tool.
        
        Args:
            query: The query to process.
            
        Returns:
            The math tool result or None if not a math query.
        """
        try:
            # Use the math_tool to process the query
            math_tool_wrapper = MathToolWrapper()
            result = math_tool_wrapper._run(query)
            
            return result
        except Exception as e:
            print(f"Math tool error: {str(e)}")
            return None
