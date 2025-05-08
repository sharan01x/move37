#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Conductor agent for the Move 37 application.
"""

from typing import Dict, Any, List, Optional, Union, Tuple, Callable
import asyncio
import threading
import re
import requests
import uuid
from datetime import datetime
import json
import os

from app.agents.base_agent import BaseAgent
from app.agents.recorder_agent import RecorderAgent
from app.agents.first_responder_agent import FirstResponderAgent
from app.agents.number_ninja_agent import NumberNinjaAgent
from app.agents.user_fact_extractor_agent import UserFactExtractorAgent
from app.agents.persephone_agent import PersephoneAgent
from app.agents.librarian_agent import LibrarianAgent
from app.agents.butterfly_agent import ButterflyAgent
from app.agents.thinker_agent import ThinkerAgent
from app.models.models import DataPackage, RecordResponse, RecallResponse, OperationType, DataType
from app.models.messages import MessageType
from app.database.conversation_db import ConversationDBInterface
from app.utils.llm_utils import parse_json_response, extract_score_from_response, extract_reasoning_from_response
from app.core.config import CONDUCTOR_LLM_PROVIDER, CONDUCTOR_LLM_MODEL, CHAT_API_URL


class ConductorAgent(BaseAgent):
    """Conductor agent for the Move 37 application."""
    
    def __init__(self, good_response_threshold: int = 85):
        """Initialize the Conductor agent."""
        # Initialize BaseAgent with required parameters
        super().__init__(
            name="Conductor",
            description="Orchestrates the flow of information between different agents in the Move 37 application.",
            role="Conductor",
            goal="Coordinate different agents to process user queries and provide accurate responses."
        )
        
        # Initialize all agent instances
        self.recorder_agent = RecorderAgent()
        self.first_responder_agent = FirstResponderAgent()
        self.number_ninja_agent = NumberNinjaAgent()
        self.persephone_agent = PersephoneAgent()
        self.user_fact_extractor_agent = UserFactExtractorAgent()
        self.librarian_agent = LibrarianAgent()
        self.butterfly_agent = ButterflyAgent()
        self.thinker_agent = ThinkerAgent()
        
        # Create group chat agents dictionary for easy access
        self.group_chat_agents = {
            "first_responder": self.first_responder_agent,
            "number_ninja": self.number_ninja_agent,
            "persephone": self.persephone_agent,
            "librarian": self.librarian_agent
        }
        
        # Initialize conversation database - we'll create user-specific instances as needed
        # This is just a placeholder for the class, not for actual use with a specific user
        self.conversation_db = ConversationDBInterface()
    
        # Define score threshold for "good" responses
        self.good_response_threshold = good_response_threshold
    
    async def process_record_operation(self, data_package: DataPackage, message_callback: Optional[Callable] = None) -> RecordResponse:
        """
        Process a record operation with optional message callbacks.
        
        Args:
            data_package: Data package containing the information to record.
            message_callback: Optional callback function for sending status updates.
            
        Returns:
            Record response containing the result of the record operation.
        """
        try:
            # Send initial status
            if message_callback:
                await message_callback({
                    "type": MessageType.STATUS_UPDATE,
                    "data": {"message": "Processing record submission..."}
                })
            
            # Extract data from the data package
            user_id = data_package.user_id
            data_type = data_package.data_type
            
            # Get text content
            transcription = None
            record_id = None
            file_path = None
            source_type = "User Submissions"
            
            if data_type == DataType.TEXT:
                # Record text content directly
                transcription = data_package.text_content
                record_id = self.recorder_agent.record_text(
                    user_id=user_id,
                    text=transcription,
                    source=source_type
                )
                
                # Analyze text for personal information asynchronously
                asyncio.create_task(self.user_fact_extractor_agent.extract_facts(transcription, user_id=user_id))
                
                # Send success status
                if message_callback:
                    await message_callback({
                        "type": MessageType.STATUS_UPDATE,
                        "data": {"message": "Record submission processed successfully", "is_final": True}
                    })
                
                return RecordResponse(
                    success=True,
                    message="Successfully recorded submission",
                    record_id=record_id
                )
            else:
                # Handle other data types (voice, file, combined)
                # TODO: Implement handling for other data types
                raise NotImplementedError(f"Data type {data_type} not yet supported")
            
        except Exception as e:
            # Send error status
            if message_callback:
                await message_callback({
                    "type": MessageType.STATUS_UPDATE,
                    "data": {"message": f"Error processing record submission: {str(e)}", "is_final": True}
                })
            raise
    
    async def process_recall_operation(self, data_package: DataPackage, message_callback: Optional[Callable] = None, attachment_file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a recall operation by coordinating with available agents.
        
        Args:
            data_package: Data package containing the query.
            message_callback: Optional callback function for sending messages.
            attachment_file_path: Optional path to an attached file (for ButterflyAgent).
            
        Returns:
            Dictionary containing the response status.
        """
        try:
            # Store the current query
            self.current_query = data_package.text_content
            
            # Send initial status
            if message_callback:
                await message_callback({
                    "type": "status_update",
                    "data": {
                        "message": "Starting recall operation...",
                        "operation_id": str(uuid.uuid4())
                    }
                })
            
            # Determine which agents to use based on target_agent
            target_agent = data_package.metadata.get('target_agent', None)
            
            # Check if target_agent is None or 'all' - now we require a specific target
            if target_agent is None or target_agent == 'all':
                error_message = "No specific agent targeted. Please specify a target agent for your query."
                
                if message_callback:
                    await message_callback({
                        "type": "status_update",
                        "data": {
                            "message": error_message,
                            "operation_id": str(uuid.uuid4()),
                            "is_final": True
                        }
                    })
                
                return {
                    "message": error_message
                }
            
            agents_to_use = {}
            
            # If the target is "thinker", use the new Thinker agent
            if target_agent == "thinker":
                agents_to_use = {"thinker": self.thinker_agent}
            # If the target is "butterfly", use the Butterfly agent
            elif target_agent == "butterfly":
                agents_to_use = {"butterfly": self.butterfly_agent}
            # If a specific agent is requested and it's in our group_chat_agents
            elif target_agent in self.group_chat_agents:
                agents_to_use = {target_agent: self.group_chat_agents[target_agent]}
            
            
            if not agents_to_use:
                error_message = f"No agents available to process the query. Invalid target agent: {target_agent}"
                
                if message_callback:
                    await message_callback({
                        "type": "status_update",
                        "data": {
                            "message": error_message,
                            "operation_id": str(uuid.uuid4()),
                            "is_final": True
                        }
                    })
                
                return {
                    "message": error_message
                }
            
            # Send status about available agents
            if message_callback:
                await message_callback({
                    "type": "status_update",
                    "data": {
                        "message": f"Processing query...",
                        "operation_id": str(uuid.uuid4())
                    }
                })
            
            # Get conversation history for agents that need it
            # Create a user-specific ConversationDBInterface instance
            user_conversation_db = ConversationDBInterface(user_id=data_package.user_id)
            conversation_history = user_conversation_db.get_recent_conversation_history(user_id=data_package.user_id)
            
            
            # Create tasks for each agent
            tasks = []
            for agent_name, agent in agents_to_use.items():
                # Create a wrapper for the message callback to format agent-specific messages
                async def agent_message_callback(message: str):
                    if message_callback:
                        await message_callback({
                            "type": "status_update",
                            "data": {
                                "message": message,
                                "operation_id": str(uuid.uuid4()),
                                "agent": agent.__class__.__name__
                            }
                        })
                
                # Set message callback for this agent
                agent.set_message_callback(agent_message_callback)
                
                # Create task for this agent with appropriate parameters
                if agent == self.first_responder_agent:
                    # First Responder needs conversation history
                    task = agent.answer_query_async(
                        data_package.text_content,
                        user_id=data_package.user_id,
                        message_callback=agent_message_callback,
                        conversation_history=conversation_history
                    )
                elif agent == self.butterfly_agent and attachment_file_path:
                    # Butterfly agent with attachment
                    task = agent.answer_query_async(
                        data_package.text_content,
                        user_id=data_package.user_id,
                        message_callback=agent_message_callback,
                        attachment_file_path=attachment_file_path
                    )
                elif agent == self.thinker_agent:
                    # Thinker agent - use the synchronous method wrapped in async
                    task = agent.answer_query_async(
                        data_package.text_content,
                        user_id=data_package.user_id,
                        message_callback=agent_message_callback
                    )
                else:
                    # Other agents don't need special parameters
                    task = agent.answer_query_async(
                        data_package.text_content,
                        user_id=data_package.user_id,
                        message_callback=agent_message_callback
                    )
                tasks.append((agent_name, task))
            
            # If no tasks were created (target agent not found), return error
            if not tasks:
                return {
                    "message": f"No agent found matching target agent: {target_agent}"
                }
            
            # Process responses as they complete
            pending = {asyncio.create_task(task): agent_name for agent_name, task in tasks}

            # Initialize a list of responses to send to quality evaluation
            responses = []
            
            try:
                while pending:
                    done, _ = await asyncio.wait(
                        pending.keys(),
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    for task in done:
                        agent_name = pending.pop(task)
                        try:
                            response = await task
                            
                            # Send response immediately if we have an answer
                            if response["answer"] and message_callback:
                                # Ensure agent_name is set in the response
                                response["agent_name"] = agent_name
                                await message_callback({
                                    "type": "agent_response",
                                    "data": response
                                })

                            # Add the response to the list for quality evaluation
                            responses.append(response)
                                
                        except Exception as e:
                            continue
            
                # All tasks are complete, send the done signal
                if message_callback:
                    await message_callback({
                        "type": "status_update",
                        "data": {
                            "message": "DONE",
                            "operation_id": str(uuid.uuid4()),
                            "is_final": True
                        }
                    })

                # Then evaluate responses and send quality updates
                asyncio.create_task(self._evaluate_responses_async(
                    data_package.text_content,
                    responses,
                    data_package.user_id,
                    message_callback
                ))
                
                # Return success message
                return {
                    "message": "Successfully processed query."
                }
                
            except Exception as e:
                return {
                    "message": f"Error processing tasks: {str(e)}"
                }
            
        except Exception as e:
            return {
                "message": f"Error processing query: {str(e)}"
            }
    
    def process_data_package(self, data_package: DataPackage) -> Union[RecordResponse, RecallResponse]:
        """
        Process a data package.
        
        Args:
            data_package: Data package to process.
            
        Returns:
            Response containing the result of the operation.
        """
        # Determine the operation type
        operation_type = data_package.operation_type
        
        # Process the data package based on the operation type
        if operation_type == OperationType.RECORD:
            return self.process_record_operation(data_package)
        elif operation_type == OperationType.RECALL:
            return self.process_recall_operation(data_package)
        else:
            # This should never happen due to the enum, but just in case
            raise ValueError(f"Invalid operation type: {operation_type}")
    
    def evaluate_responses(self, query: str, responses: List[str]) -> List[Tuple[int, str]]:
        """
        Evaluate multiple responses to a query in a single LLM call.
        
        Args:
            query: Original query
            responses: List of responses to evaluate
            
        Returns:
            List of (score, reasoning) tuples for each response
        """
        # Define system prompt for evaluation
        system_prompt = """You are a Quality Assurance evaluator responsible for determining 
        how well responses answer queries. Your job is to be objective and honest."""
        
        # Format responses for the prompt
        responses_json = json.dumps([
            {"index": i, "response": response}
            for i, response in enumerate(responses)
        ], ensure_ascii=False)
        
        # Define user prompt with query and responses
        query_json = json.dumps(query, ensure_ascii=False)
        
        user_prompt = f"""
        Evaluate how well each of the following responses answers the original query. You are to evaluate only the answers provided by the agents, do not try to answer the query yourself.

        Original query: {query_json}

        Responses:
        {responses_json}

        Return a score from 0 to 100 for each response:
        - 0: The response does not answer the query at all. This score will need to be assigned to responses that include "I don't know" or "I don't recall". 
        - 100: The response perfectly answers the query (only ONE response can get 100)
        - Between 0-100: The response partially answers the query but a higher number indicates that it's more complete
        - In case the user query is not a question but a statement, as long as the response is grammatically correct and complete, it can get a high score
        - In case the answers provided by agents are conversational, that's okay, don't lower the score for that.
        - Some answers will be based on information that the agents have access to, such as the user's profile or the conversation history. That's okay, don't lower the score for that thinking that the answer is not correct.

        Return your evaluation as a JSON object with the following structure:
        {{
            "evaluations": [
                {{
                    "response_index": 0,
                    "score": [numeric score from 0-100],
                    "reasoning": "[brief explanation for the score]"
                }},
                ...
            ]
        }}

        Your response must ONLY contain the valid JSON object and nothing else. Do not include any explanation or markdown formatting.

        Make sure the JSON is properly formatted and can be parsed by Python's json.loads() function.

        IMPORTANT: Your response must be entirely in English. Do not include any non-English text in your response.
        """
        
        # Call the LLM to get the evaluation
        try:
            # Common message structure for all providers
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Using Ollama API with the Conductor's LLM configuration
            try:
                # Ollama API endpoint from config
                url = CHAT_API_URL
                
                # Prepare the payload for Ollama
                payload = {
                    "model": CONDUCTOR_LLM_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.0}
                }
                
                # Make the API call
                response = requests.post(url, json=payload)
                response.raise_for_status()  # Raise exception for non-200 responses
                
                # Extract the content from the response
                response_json = response.json()
                response_text = response_json.get("message", {}).get("content", "")
                
                if not response_text:
                    # Try alternative response format if the above doesn't work
                    response_text = response_json.get("response", "")
                    
                if not response_text:
                    raise ValueError("Empty response from Ollama")
                    
            except requests.RequestException as e:
                print(f"Ollama API request failed: {e}")
                raise
            except ValueError as e:
                print(f"Failed to parse Ollama response: {e}")
                raise
            
            # Try to parse the response as JSON
            result = parse_json_response(response_text)
            if result and "evaluations" in result:
                evaluations = result["evaluations"]
                # Sort evaluations by response_index to ensure correct order
                evaluations.sort(key=lambda x: x["response_index"])
                
                # Extract scores and reasoning
                results = []
                for eval_data in evaluations:
                    score = eval_data.get("score", 0)
                    reasoning = eval_data.get("reasoning", "No reasoning provided")
                    
                    # Ensure score is an integer and in the valid range
                    try:
                        score = int(score)
                        score = max(0, min(100, score))  # Clamp to 0-100 range
                    except (ValueError, TypeError):
                        score = extract_score_from_response(str(score), default_score=0, min_value=0, max_value=100)
                    
                    results.append((score, reasoning))
                
                return results
            else:
                # Fallback to regex parsing if JSON parsing fails
                # Extract evaluations using regex
                results = []
                for i in range(len(responses)):
                    # Try to find score and reasoning for this response
                    score_match = re.search(f'"response_index":\s*{i}.*?"score":\s*(\d+)', response_text)
                    reasoning_match = re.search(f'"response_index":\s*{i}.*?"reasoning":\s*"([^"]+)"', response_text)
                    
                    score = 0
                    reasoning = "No reasoning provided"
                    
                    if score_match:
                        try:
                            score = int(score_match.group(1))
                            score = max(0, min(100, score))
                        except (ValueError, TypeError):
                            score = extract_score_from_response(str(score), default_score=0, min_value=0, max_value=100)
                    
                    if reasoning_match:
                        reasoning = reasoning_match.group(1)
                    
                    results.append((score, reasoning))
                
                return results
                
        except Exception as e:
            print(f"Error in response evaluation: {e}")
            # Return default values for all responses in case of error
            return [(0, f"Error evaluating response: {str(e)}")] * len(responses)

    async def _process_conversation_for_user_facts(self, query: str, direct_response: str) -> None:
        """
        Process a conversation for user facts asynchronously.
        
        Args:
            query: Original user query
            direct_response: Agent's response
        """
        # Format the conversation for fact extraction
        conversation_text = f"User Query: {query}\nAgent Response: {direct_response}"
        # Call fact extractor asynchronously
        await self.user_fact_extractor_agent.extract_facts(conversation_text)

    async def _evaluate_responses_async(self, query: str, responses: List[Dict[str, Any]], user_id: str, message_callback: Optional[Callable] = None) -> None:
        """
        Evaluate responses asynchronously and update their scores.
        
        Args:
            query: Original user query
            responses: List of response dictionaries from agents
            user_id: ID of the user making the query
            message_callback: Optional callback function for sending messages
        """
        try:
            # Collect responses that need evaluation
            responses_to_evaluate = []
            response_indices = []
            
            for i, response in enumerate(responses):
                answer = response.get("answer")
                if answer and not response.get("response_score"):
                    responses_to_evaluate.append(answer)
                    response_indices.append(i)
            
            if responses_to_evaluate:
                # Evaluate all responses at once
                evaluations = self.evaluate_responses(query, responses_to_evaluate)
                
                # Update all responses with their scores
                quality_updates = []
                for i, (score, reasoning) in enumerate(evaluations):
                    response_idx = response_indices[i]
                    responses[response_idx]["response_score"] = score
                    responses[response_idx]["quality_reasoning"] = reasoning
                    
                    # Ensure we're using agent_name consistently
                    quality_updates.append({
                        "agent_name": responses[response_idx].get("agent_name"),
                        "response_score": score,
                        "quality_reasoning": reasoning
                    })
                
                # Send all quality updates at once
                if message_callback and quality_updates:
                    await message_callback({
                        "type": "quality_updates",
                        "data": quality_updates
                    })
                
                # Store all conversations at once
                for i, response in enumerate(responses):
                    if response.get("answer"):
                        self._store_conversation_async(
                            user_id=user_id,
                            query=query,
                            direct_response=response["answer"],
                            agent_name=response.get("agent_name")
                        )
                        
        except Exception as e:
            print(f"Error in async response evaluation: {e}")

    def _store_conversation_async(self, user_id: str, query: str, direct_response: str, agent_name: Optional[str] = None) -> None:
        """
        Store a conversation asynchronously.
        
        Args:
            query: Original user query
            direct_response: Agent's response
            agent_name: Name of the agent that provided the response
        """
        def store_conversation():
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Create a user-specific conversation database to ensure we're storing in the right folder
                user_specific_db = ConversationDBInterface(user_id=user_id)
                user_specific_db.add_conversation(
                    user_id=user_id,
                    user_query=query,
                    agent_response=direct_response,
                    agent_name=agent_name,
                    timestamp=timestamp
                )
            except Exception as e:
                print(f"Error in async conversation storage: {e}")
        
        # Start a new thread for the storage operation
        thread = threading.Thread(target=store_conversation)
        thread.daemon = True  # Make the thread a daemon so it doesn't block program exit
        thread.start()
