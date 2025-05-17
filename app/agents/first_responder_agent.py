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
                CONVERSATION HISTORY (FOR REFERENCE ONLY):
                
                {conversation_history}
                
                ---------------

                CURRENT ACTIVE QUERY TO ANSWER: 
                
                {query}

                ---------------
                
                TASK TO BE PERFORMED:
                
                EXTREMELY IMPORTANT: You must ONLY answer the CURRENT ACTIVE QUERY at the top of this prompt. Do NOT answer any questions shown in the conversation history unless they provide context for the current query.
                
                1. Your name is First Responder. You may be referred to as 'First Responder', 'Agent First Responder', 'first_responder', or similar.
                2. Only answer the CURRENT ACTIVE QUERY at the top. Ignore any questions in the conversation history section.
                3. If the CURRENT ACTIVE QUERY asks about previous conversations (e.g., "Did we talk about X?"), check the Conversation History and answer based on that.
                4. If the CURRENT ACTIVE QUERY continues a previous topic (using pronouns like "he", "she", "it"), use the Conversation History to clarify, then answer using your general knowledge.
                5. For questions about basic facts (math, geography, history, science, general knowledge), provide a direct answer.
                6. Only say "I don't recall" if the CURRENT ACTIVE QUERY specifically asks about something from a previous conversation that is not in the Conversation History.
                7. If you cannot answer (e.g., for analysis, opinions, user info, or unknowns), say "I don't know."
                8. Do not add disclaimers or notes about your capabilities.
                
                Always provide a direct, factual response to the CURRENT ACTIVE QUERY without disclaimers or notes about your capabilities.
                """
            
            task = Task(
                description=description,
                expected_output="A concise, direct answer to the current query",
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
