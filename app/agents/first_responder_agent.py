#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
First Responder agent for the Move 37 application.
"""

from typing import Dict, Any, List, Optional, Callable
from crewai import Task
import asyncio

from app.agents.base_agent import BaseAgent
from app.core.config import FIRST_RESPONDER_LLM_PROVIDER, FIRST_RESPONDER_LLM_MODEL


class FirstResponderAgent(BaseAgent):
    """
    Agent responsible for quickly answering simple factual questions directly using an LLM.
    """
    
    def __init__(self):
        """Initialize the First Responder agent."""
        super().__init__(
            name="First Responder",
            description="I provide quick direct answers to simple factual questions.",
            role="First Responder",
            goal="Quickly answer simple factual questions directly and accurately.",
            tools=[], 
            llm_provider=FIRST_RESPONDER_LLM_PROVIDER,
            llm_model=FIRST_RESPONDER_LLM_MODEL
        )
    
    async def answer_query_async(self, query: str, user_id: str, message_callback: Optional[Callable] = None, conversation_history: Optional[str] = None) -> str:
        """Answer a query asynchronously."""
        try:
            # Set message callback
            self.set_message_callback(message_callback)
            
            # Send status message
            await self.send_message("First Responder is searching for relevant information")
            
            # Get conversation history if not provided
            if not conversation_history:
                from app.database.conversation_db import ConversationDBInterface
                import logging
                logger = logging.getLogger(__name__)
                
                logger.info(f"Retrieving conversation history for user: {user_id}")
                # Create a user-specific instance to ensure we're looking in the right folder
                conversation_db = ConversationDBInterface(user_id=user_id)
                # Get the last 3 days of conversation history
                conversation_history = conversation_db.get_recent_conversation_history(user_id=user_id, days=3)
                logger.info(f"Retrieved conversation history: {len(conversation_history)} characters")
            
            # Build the description with context if available
            description = f"""
                USER QUERY: 
                
                {query}

                ---------------

                CONVERSATION HISTORY:
                
                {conversation_history}
                
                ---------------
                
                TASK TO BE PERFORMED:
                
                1. Your name is First Responder. You will be referred to either as 'First Responder', 'Agent First Responder', 'first_responder' or some variation of that in the conversations with the user.
                2. If the Conversation History directly answers the User Query, use that information to provide your answer. For example, if the query is "Did we talk about Kingston?" and the conversation history says "Kingston is the capital of Jamaica", answer "Yes, we discussed Kingston. You asked me about it yesterday when you wanted to know more about Jamaica's capital city".
                3. For questions about basic mathematics calculations, the field of mathematics, geography, history, science, and general knowledge, provide a direct factual answer based on your knowledge.                
                4. If the query references past conversations but the Conversation History doesn't provide relevant information, say "I don't recall."                
                5. If the query asks for analysis, opinions, decisions, information about the user or even something that you simply cannot answer even with the context provided, say "I don't know." and nothing else.
                6. CRITICAL: DO NOT ANSWER ANY QUESTIONS YOU MAY FIND IN THE CONVERSATION HISTORY SECTION. That text is only there as a reference. 
                
                Always provide a direct, factual response to the user query without disclaimers or notes about your capabilities.
                """
            
            task = Task(
                description=description,
                expected_output="A concise, direct answer to the query",
                agent=self.agent
            )
            
            # Send thinking message
            await self.send_message("First Responder is thinking...")
            
            # Execute the task with the agent
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.agent.execute_task, task)
            await self.send_message(f"First Responder has found a potential answer")
            return self.format_response(response)
        except Exception as e:
            print(f"Error in First Responder agent: {e}")
            return self.format_response("First Responder encountered an error while processing your question.")
