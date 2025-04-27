#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Persephone agent for the Move 37 application.
Specializes in answering queries related to user facts stored in the database.
"""

from typing import Dict, Any, List, Optional, Callable
from crewai import Task
import asyncio

from app.agents.base_agent import BaseAgent
from app.core.config import PERSEPHONE_LLM_PROVIDER, PERSEPHONE_LLM_MODEL
from app.database.user_facts_db import UserFactsDBInterface


class PersephoneAgent(BaseAgent):
    """
    Agent specialized in answering queries related to user facts stored in the database.
    """
    
    def __init__(self):
        """Initialize the Persephone agent."""
        super().__init__(
            name="Persephone",
            description="I specialize in answering questions about the user based on stored facts.",
            role="Personal Information Specialist",
            goal="Provide accurate responses about the user based on stored facts.",
            tools=[], 
            llm_provider=PERSEPHONE_LLM_PROVIDER,
            llm_model=PERSEPHONE_LLM_MODEL
        )
        # We'll create user-specific instances as needed in the methods
    
    async def answer_query_async(self, query: str, user_id: str, message_callback: Optional[Callable] = None) -> str:
        """Answer a query asynchronously."""
        try:
            # Set message callback
            self.set_message_callback(message_callback)
            
            # Send status message
            await self.send_message("Persephone is searching for relevant user information...")
            
            # Search for relevant facts in the database using our improved search
            # Create a user-specific instance to ensure we're looking in the right folder
            user_specific_db = UserFactsDBInterface(user_id=user_id)
            
            # Log the search attempt
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Searching for facts relevant to: {query}")
            
            # Search for relevant facts using our custom semantic search implementation
            await self.send_message("Persephone is searching for relevant user information...")
            relevant_facts = user_specific_db.semantic_search(query, top_k=10)
            logger.info(f"Found {len(relevant_facts)} facts relevant to the query using semantic search")
            
            # If no facts found, try to search with a more general query
            if not relevant_facts:
                await self.send_message("Persephone is looking deeper into user information...")
                # Extract key terms from the query to broaden the search
                import re
                key_terms = re.findall(r'\b\w{4,}\b', query.lower())
                if key_terms:
                    for term in key_terms:
                        logger.info(f"Searching with broader term: {term}")
                        additional_facts = user_specific_db.semantic_search(term, top_k=3)
                        relevant_facts.extend(additional_facts)
                        logger.info(f"Found {len(additional_facts)} additional facts with term: {term}")
                
                # If still no facts, fall back to getting a subset of all facts
                if not relevant_facts:
                    logger.info("No relevant facts found, falling back to a subset of all facts")
                    all_facts = user_specific_db.get_all_facts()
                    # Take the most recent facts (up to 20)
                    relevant_facts = sorted(all_facts, key=lambda x: x.get('created_at', ''), reverse=True)[:50]
                    logger.info(f"Using {len(relevant_facts)} recent facts as fallback")
            
            # Format facts for the prompt
            facts_context = ""
            if relevant_facts:
                facts_context = "Here are the facts I know about the user:\n\n"
                for i, fact in enumerate(relevant_facts, 1):
                    # Format the date
                    created_date = ""
                    try:
                        from datetime import datetime
                        created_date = datetime.fromisoformat(fact['created_at']).strftime("%B %d, %Y")
                    except (ValueError, KeyError):
                        created_date = "unknown date"
                    
                    facts_context += f"{i}. {fact['fact']} (learned on {created_date})\n"


            # Get user preferences
            user_preferences = "No specific preferences found."
            try:
                preference_facts = user_specific_db.get_facts_by_category("preference")
                if preference_facts:
                    user_preferences = "Here are the user's preferences:\n\n"
                    for i, pref in enumerate(preference_facts, 1):
                        # Format the date
                        created_date = ""
                        try:
                            from datetime import datetime
                            created_date = datetime.fromisoformat(pref['created_at']).strftime("%B %d, %Y")
                        except (ValueError, KeyError):
                            created_date = "unknown date"
                        user_preferences += f"{i}. {pref['fact']} (stated on {created_date})\n"
            except Exception as e:
                logger.error(f"Error fetching user preferences: {e}")
                user_preferences = "Could not retrieve user preferences due to an error."
            
            
            # Build the description with facts context
            description = f"""
                USER QUERY:

                {query}
                
                _________________________________________________________________________________________

                RELEVANT USER FACTS:

                {facts_context}

                _________________________________________________________________________________________

                USER PREFERENCES:

                {user_preferences}

                _________________________________________________________________________________________

                INSTRUCTIONS TO PERFORM THE TASK:
                
                1. Your name is Persephone and you may be referred to as Agent Persephone or Persephone. You are a personal information specialist and you've been provided with a list of facts about the user above in the RELEVANT USER FACTS section.
                2. If the question was about finding some facts about the user, answer the USER QUERY only based on the RELEVANT USER FACTS provided.
                3. If multiple RELEVANT USER FACTS answer the USER QUERY, synthesize them into a coherent answer.
                6. If the RELEVANT USER FACTS only partially answer the query, provide what you know and acknowledge the limitations.
                7. If there are very few RELEVANT USER FACTS about the user, you can assume that you don't know them very well. So you may be more formal in your responses. But as you know more RELEVANT USER FACTS about the user, you can become more friendly or even be funny. But never be sarcastic or mean.
                8. Do not mention "facts" or "database" in your response - speak as if you simply know this information about the user.
                9. If the question is about anything other than the things listed in the RELEVANT USER FACTS, just respond with how you think the answer relates to what you know about the user. But don't force a connection if you can't find one, in such cases, just respond with "I don't know."
                10. Formulate your response while keeping in mind the usre's preferences as described in the USER PREFERENCES section. For instance, if the user doesn't like something, don't mention it in your response.

                Your response must always be short and to the point, in the first person voice and addressing the user.
            """
            
            # Create and execute the task
            task = Task(
                description=description,
                expected_output="A friendly, personalized response based on user facts",
                agent=self.agent
            )
            
            # Execute the task with the agent
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.agent.execute_task, task)
            
            # Send final status
            await self.send_message("Persephone has found relevant information.")
            
            return self.format_response(response)
            
        except Exception as e:
            print(f"Error in Persephone agent: {e}")
            return self.format_response("I encountered an error while searching for information.") 