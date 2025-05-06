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
                CURRENT ACTIVE QUERY TO ANSWER: 
                
                {query}

                ---------------

                CONVERSATION HISTORY (FOR REFERENCE ONLY):
                
                {conversation_history}
                
                ---------------
                
                TASK TO BE PERFORMED:
                
                EXTREMELY IMPORTANT: You must ONLY answer the CURRENT ACTIVE QUERY at the top of this prompt. Do NOT answer any questions shown in the conversation history unless they provide context for the current query.
                
                1. Your name is First Responder. You will be referred to either as 'First Responder', 'Agent First Responder', 'first_responder' or some variation of that in the conversations with the user.
                
                2. If the CURRENT ACTIVE QUERY is about what was discussed in previous conversations (e.g. "Did we talk about X?"), check the Conversation History and answer based on that.
                
                3. If the CURRENT ACTIVE QUERY continues a topic from previous messages (using pronouns like "he", "she", "it"), use the conversation history to determine what these refer to, then answer the query using your general knowledge.
                
                4. For questions about basic mathematics, geography, history, science, and general knowledge, provide a direct factual answer based on your knowledge.
                
                5. Only say "I don't recall" if the CURRENT ACTIVE QUERY explicitly asks about a previous conversation that isn't in the conversation history (e.g. "What did you tell me about X yesterday?").
                
                6. If the CURRENT ACTIVE QUERY asks for analysis, opinions, decisions, information about the user, or something you simply cannot answer, say "I don't know."
                
                7. CRITICAL: 
                   - Ignore any questions that appear ONLY in the conversation history section
                   - Do NOT answer the most recent question in the conversation history
                   - ONLY answer the CURRENT ACTIVE QUERY at the top
                
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
