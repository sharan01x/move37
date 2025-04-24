#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
User Fact Extractor Agent for analyzing text and extracting personal information.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.config import USER_FACT_EXTRACTOR_LLM_PROVIDER, USER_FACT_EXTRACTOR_LLM_MODEL
from app.utils.llm import get_llm_response
from app.database.user_facts_db import UserFactsDBInterface

logger = logging.getLogger(__name__)

class UserFactExtractorAgent:
    """Agent for extracting user facts from text."""

    def __init__(self):
        """Initialize the UserFactExtractorAgent."""
        self.llm_provider = USER_FACT_EXTRACTOR_LLM_PROVIDER
        self.llm_model = USER_FACT_EXTRACTOR_LLM_MODEL
        # We'll initialize user_facts_db instances per user as needed
    
    async def extract_facts(self, text: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract facts from text asynchronously.
        
        Args:
            text: The text to analyze.
            user_id: The ID of the user whose facts are being extracted.
                    If provided, facts will be stored in a user-specific folder.
            
        Returns:
            A list of extracted facts.
        """
        # Create a task to extract facts
        loop = asyncio.get_event_loop()
        task = loop.create_task(self._extract_facts_task(text, user_id))
        
        # Return an empty list immediately, the task will run in the background
        return []
    
    async def _extract_facts_task(self, text: str, user_id: Optional[str] = None) -> None:
        """Background task to extract facts and store them in the database.
        
        Args:
            text: The text to analyze.
            user_id: The ID of the user whose facts are being extracted.
                    If provided, facts will be stored in a user-specific folder.
        """
        try:
            # Extract facts using LLM
            facts = await self._extract_facts_with_llm(text, user_id=user_id)
            
            # Initialize user-specific database interface
            user_facts_db = UserFactsDBInterface(user_id=user_id)
            
            # Store facts in the database
            for fact in facts:
                user_facts_db.add_fact(
                    fact=fact["fact"],
                    category=fact["category"],
                    source_text=text,
                    confidence=fact.get("confidence", 1.0)
                )
            
            logger.info(f"Extracted and stored {len(facts)} facts from text for user {user_id}")
        except Exception as e:
            logger.error(f"Error extracting facts: {e}")
    
    async def _extract_facts_with_llm(self, text: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract facts from text using LLM.
        
        Args:
            text: The text to analyze.
            user_id: The ID of the user whose facts are being extracted.
                    If provided, existing facts will be retrieved from a user-specific folder.
            
        Returns:
            A list of extracted facts.
        """
        # Create the prompt for the LLM
        prompt = self._create_extraction_prompt(text, user_id=user_id)
        
        # Get the response from the LLM
        response = await get_llm_response(
            provider=self.llm_provider,
            model=self.llm_model,
            prompt=prompt,
            temperature=0.2,
            max_tokens=1000
        )
        
        # Parse the response to extract facts
        facts = self._parse_facts_from_response(response)
        
        return facts
    
    def _create_extraction_prompt(self, text: str, user_id: Optional[str] = None) -> str:
        """Create a prompt for extracting facts from text.
        
        Args:
            text: The text to analyze.
            user_id: The ID of the user whose facts are being extracted.
                    If provided, existing facts will be retrieved from a user-specific folder.
            
        Returns:
            The prompt for the LLM.
        """
        # Retrieve relevant existing facts
        existing_facts = self._get_relevant_existing_facts(text, user_id=user_id)
        
        existing_facts_context = ""
        if existing_facts:
            existing_facts_context = "Here are some facts I already know about the user:\n"
            for fact in existing_facts:
                # Convert ISO timestamp to a more readable format
                created_date = datetime.fromisoformat(fact['created_at']).strftime("%B %d, %Y")
                existing_facts_context += f"- {fact['fact']} (confidence: {fact['confidence']}, recorded at: {created_date})\n"
            existing_facts_context += "\n"
        
        return f"""You are an AI assistant that extracts personal information and preferences from text.
Your task is to analyze the following text and identify any facts about the user, such as:

1. Personal information (name, age, location, occupation, etc.)
2. Personal preferences (likes, dislikes, favorites)
3. Personal habits and routines
4. Personal goals and aspirations
5. Personal relationships and social connections (spouse, parents, relatives, children, pets)
6. Other facts about the user

Known Facts:
__________________

{existing_facts_context}

__________________

When analyzing the text, please:
1. Identify new facts about the user that are not already mentioned in the known facts
2. Identify facts about the user that contradict known facts (and note the contradiction by adding something like "...though he previously didn't like it" or "...but she has been a vegetarian for a short while"). 
3. Be careful and call a fact a contradiction only if it is exactly the same. For example, "The user likes beaches" contradicts "The user does't like beaches", but "The user like vanilla ice cream" does not contradict "The user likes strawberry ice cream" as it is possible for a person to like more than one flavour of ice cream.
4. In cases where a fact is mentioned about groups of things, create a fact for each. For example, if the text mentions "John went to the pub with his best friends from school, Mike and Sarah", create two facts: "John went to the pub with his best friend from school, Mike" and "John went to the pub with his best friend from school, Sarah".

For each personal fact you identify, provide:
- The fact itself (a clear, concise statement) that usually starts with "The user", such as "The user's name is John" or if the user'sname is known, then something like "John played football in high school" or "John is a software engineer"
- The category it belongs to (personal_info, preference, habit, goal, relationship, other)
- A confidence score (0 to 100) indicating how certain you are about this fact

Only extract facts that are explicitly stated or can be directly inferred with high confidence. Do not make assumptions or extract facts with low confidence.

Format your response as a JSON array of objects, each with "fact", "category", and "confidence" fields.

Text to analyze:
"{text}"

Facts:"""
    
    def _parse_facts_from_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse facts from the LLM response.
        
        Args:
            response: The LLM response.
            
        Returns:
            A list of extracted facts.
        """
        try:
            # Try to parse the response as JSON
            import json
            facts = json.loads(response)
            
            # Validate the facts
            if not isinstance(facts, list):
                return []
            
            valid_facts = []
            for fact in facts:
                if isinstance(fact, dict) and "fact" in fact and "category" in fact:
                    # Ensure the fact has all required fields
                    valid_fact = {
                        "fact": fact["fact"],
                        "category": fact["category"],
                        "confidence": fact.get("confidence", 1.0)
                    }
                    valid_facts.append(valid_fact)
            
            return valid_facts
        except json.JSONDecodeError:
            # If the response is not valid JSON, try to extract facts using regex
            import re
            
            facts = []
            
            # Look for patterns like: "Fact: ..., Category: ..., Confidence: ..."
            fact_pattern = r'(?:Fact|"fact"):\s*"?([^"]+)"?,\s*(?:Category|"category"):\s*"?([^"]+)"?,\s*(?:Confidence|"confidence"):\s*([0-9.]+)'
            matches = re.findall(fact_pattern, response, re.IGNORECASE)
            
            for match in matches:
                fact, category, confidence = match
                facts.append({
                    "fact": fact.strip(),
                    "category": category.strip(),
                    "confidence": float(confidence)
                })
            
            return facts 
        
    def _get_relevant_existing_facts(self, text: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get existing facts that might be relevant to the new text.
        
        Args:
            text: The text to analyze.
            user_id: The ID of the user whose facts are being analyzed.
                    If provided, facts will be retrieved from a user-specific folder.
            
        Returns:
            A list of relevant existing facts.
        """
        try:
            # Create a user-specific database interface
            user_facts_db = UserFactsDBInterface(user_id=user_id)
            
            # First, try semantic search to find relevant facts
            relevant_facts = user_facts_db.search_facts(text, top_k=10)
            
            # If we don't have many results, include some high-confidence facts from each category
            if len(relevant_facts) < 2:
                categories = ["personal_info", "preference", "habit", "goal", "relationship", "other"]
                for category in categories:
                    category_facts = user_facts_db.get_facts_by_category(category)
                    # Sort by confidence and take top 2
                    category_facts.sort(key=lambda x: x.get("confidence", 0), reverse=True)
                    relevant_facts.extend(category_facts[:2])
            
            # Remove duplicates
            unique_facts = []
            fact_ids = set()
            for fact in relevant_facts:
                if fact["id"] not in fact_ids:
                    unique_facts.append(fact)
                    fact_ids.add(fact["id"])
            
            return unique_facts
        except Exception as e:
            logger.error(f"Error getting relevant existing facts: {e}")
            return []

