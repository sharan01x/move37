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

from app.agents.base_agent import BaseAgent
from app.core.config import NUMBER_NINJA_LLM_PROVIDER, NUMBER_NINJA_LLM_MODEL
from app.utils.llm_utils import parse_json_response, extract_json_from_llm_response
from app.tools.math_tool import math_tool


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
            tools=[math_tool], 
            llm_provider=NUMBER_NINJA_LLM_PROVIDER,
            llm_model=NUMBER_NINJA_LLM_MODEL
        )
    
    async def answer_query_async(self, query: str, user_id: str, message_callback: Optional[Callable] = None) -> Union[str, Dict[str, Any]]:
        """
        Answer a query, determining if it's mathematics-related and providing a solution if it is.
        
        Args:
            query: Query to answer.
            user_id: Optional user ID.
            message_callback: Optional callback function to send interim messages during processing.
            
        Returns:
            JSON formatted response with solution and explanation.
        """
        try:
            # Set message callback
            self.set_message_callback(message_callback)
            
            # Send status message
            await self.send_message("Number Ninja is analyzing if this question can be solved with our math tool...")
            
            # First try to solve it using our Math Tool for faster calculations
            math_result = math_tool.func(query)
            
            # If it's a math query and we got a valid answer with our math tool, return immediately
            if math_result.get("is_math_tool_query", False) and math_result.get("answer") is not None and not math_result.get("requires_llm", False):
                await self.send_message(f"Number Ninja has found the answer: {math_result.get('answer')}")
                return self.format_response(
                    math_result.get("answer"),
                    response_score=100 if not math_result.get("requires_llm") else None,
                    is_math_tool_query=True
                )
            
            # If it's not a math query at all, return that result
            if not math_result.get("is_math_tool_query", False):
                return self.format_response(math_result.get("answer", "I don't know"))
            
            # For more complex math problems that require the LLM
            await self.send_message("Number Ninja is processing a mathematics problem that requires language processing...")
            
            # Build the description with context if available
            description = f"""
                User Query: {query}
                ---------------
                INSTRUCTIONS:
                1. For questions about mathematics, provide direct factual answers based on your knowledge.
                2. If you cannot answer the query, say "I don't know."
                Always provide a direct, factual response to the user query without disclaimers or notes about your capabilities.
            """
            task = Task(
                description=description,
                expected_output="A response with the solution to the mathematics problem",
                agent=self.agent
            )
            
            # Execute the task with the agent
            loop = asyncio.get_event_loop()
            raw_response = await loop.run_in_executor(None, self.agent.execute_task, task)
            
            return self.format_response(
                raw_response.strip() if raw_response else "I don't know",
                response_score=1.0,
                is_math_tool_query=True
            )
            
        except Exception as e:
            print(f"Error in Number Ninja agent: {e}")
            return self.format_response(
                "I don't know",
                response_score=0.0,
                is_math_tool_query=True
            )
