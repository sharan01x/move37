#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Librarian agent for the Move 37 application.
Specializes in answering queries related to contents of files uploaded by the user.
"""

from typing import Dict, Any, List, Optional, Callable
from crewai import Task
import asyncio
import logging
from datetime import datetime
import json
import os

from app.agents.base_agent import BaseAgent
from app.core.config import LIBRARIAN_LLM_PROVIDER, LIBRARIAN_LLM_MODEL
from app.database.file_db import FileDBInterface
from app.utils.file_vectorizer import FileVectorizer


class LibrarianAgent(BaseAgent):
    """
    Agent specialized in answering queries related to contents of files uploaded by the user.
    """
    
    def __init__(self):
        """Initialize the Librarian agent."""
        super().__init__(
            name="Librarian",
            description="I specialize in answering questions about the contents of files uploaded by the user.",
            role="File Content Specialist",
            goal="Provide accurate responses about the contents of files uploaded by the user.",
            tools=[], 
            llm_provider=LIBRARIAN_LLM_PROVIDER,
            llm_model=LIBRARIAN_LLM_MODEL
        )
        # Document context tracking for each user
        self.document_context = {}  # Format: {user_id: {"document": filename, "timestamp": datetime, "active": bool}}
    
    def set_document_context(self, user_id: str, document: str, active: bool = True):
        """Set the active document context for a user."""
        self.document_context[user_id] = {
            "document": document,
            "timestamp": datetime.now(),
            "active": active
        }
        print(f"Set document context for user {user_id}: {document}")
    
    def clear_document_context(self, user_id: str):
        """Clear or deactivate the document context for a user."""
        if user_id in self.document_context:
            self.document_context[user_id]["active"] = False
            print(f"Cleared document context for user {user_id}")
    
    def get_document_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the current document context for a user, if active."""
        context = self.document_context.get(user_id)
        if context and context.get("active", False):
            # Check for expiration (optional - can implement time-based expiry)
            return context
        return None
    
    async def answer_query_async(self, query: str, user_id: str, message_callback: Optional[Callable] = None) -> str:
        """Answer a query asynchronously using a file-based RAG approach with document context memory."""
        try:
            # Set message callback
            self.set_message_callback(message_callback)
            
            # Initialize logger
            logger = logging.getLogger(__name__)
            
            # --- Step 1: Check for active document context ---
            active_context = self.get_document_context(user_id)
            context_document = active_context.get("document") if active_context else None
            
            # If we have an active document context, try searching there first
            if context_document:
                logger.info(f"Using active document context: {context_document}")
                print(f"Using active document context: {context_document}")
                
                await self.send_message(f"Librarian is searching in '{context_document}'...")
                
                # Variable to track if we should switch to global search
                switch_to_global_search = False
                
                # Try searching within the context document
                context_results = await self._search_specific_document(
                    query=query, 
                    user_id=user_id, 
                    document_name=context_document
                )
                
                # If we found relevant information in the context document, use it
                if context_results:
                    logger.info(f"Found relevant information in context document")
                    print(f"Found relevant information in context document")
                    
                    # Get the document context
                    file_context = context_results["file_context"]
                    
                    # Build LLM prompt and generate response
                    description = f"""
                        USER QUERY:

                        {query}

                        _________________________________________________________________________________________

                        RELEVANT INFORMATION FROM USER'S FILES:

                        {file_context}

                        _________________________________________________________________________________________

                        INSTRUCTIONS TO PERFORM THE TASK:

                        1.  **Your Role:** You are Librarian, an AI assistant specialized in retrieving and synthesizing information *exclusively* from the user's documents provided above in the 'RELEVANT INFORMATION FROM USER'S FILES' section.
                        2.  **Analyze:** Carefully read the USER QUERY and the provided RELEVANT INFORMATION FROM USER'S FILES to find information relevant to the query. 
                        3.  **No answer found:** If no relevant information is found to answer the query, just let the user know by saying something like: "I couldn't find the information you were looking for. Try asking that differently." and nothing else.
                        3.  **Answer Source:** Base your answer *strictly* and *only* on the information presented in the RELEVANT INFORMATION FROM USER'S FILES. Do **NOT** use any external knowledge or make assumptions beyond the provided text.
                        4.  **Synthesize:** If multiple text passages from the same source document provide relevant information, combine them into a single, coherent, and concise answer. 
                        5.  **Acknowledge Limits:** If the provided information only partially answers the query, state what you found and clearly mention what information is missing or couldn't be confirmed from the context.
                        6.  **No Invention / Handling Absence of Information:** If the answer is **not present** in the provided context, DO NOT invent information. You MUST respond by stating that you couldn't find the relevant information in the provided files. Use phrasing like: "I couldn't find information about that in the files I searched." or "The provided documents don't seem to contain details about [topic of the query]."
                        7.  **Tone & Style:** Be helpful, factual, and concise. Speak in the first person ("I found...", "It seems..."). Address the user directly but maintain a professional and informative tone.
                        8.  **Formatting:** Respond in plain text. Do not use markdown code. 
                        9.  **Final Output:** Your final output should *only* be the direct response to the user, fulfilling their query based on the constraints above.

                        Now, answer the user's query based on the instructions provided.
                    """
                    
                    # Create and execute the task
                    task = Task(
                        description=description,
                        expected_output="A concise answer synthesized exclusively from the provided file content.",
                        agent=self.agent
                    )
                    
                    await self.send_message("Librarian is formulating the response...")
                    
                    # Execute the task with the agent
                    loop = asyncio.get_event_loop()
                    try:
                        response = await loop.run_in_executor(None, self.agent.execute_task, task)
                        await self.send_message("Librarian has prepared the response.")
                        
                        # Check if the LLM couldn't find an answer in the context document
                        # This is an additional signal that we should try searching all documents
                        no_info_phrases = [
                            "couldn't find",
                            "could not find",
                            "don't have",
                            "do not have",
                            "no information",
                            "not able to find",
                            "doesn't contain",
                            "does not contain",
                            "no relevant information",
                            "doesn't mention",
                            "not mentioned",
                            "no details"
                        ]
                        
                        response_lower = response.lower()
                        if any(phrase in response_lower for phrase in no_info_phrases):
                            print(f"LLM couldn't find information in context document, trying all documents...")
                            # Don't keep the context active - we'll reset it when we find a better document
                            self.clear_document_context(user_id)
                            # Continue with global search instead of returning here
                            switch_to_global_search = True
                        else:
                            # If we're here, we found a good answer in the context document
                            # Keep the document context active
                            self.set_document_context(user_id, context_document)
                            
                            # Return the response with context
                            return self.format_response(response, context_document=context_document)
                    except Exception as task_error:
                        logger.error(f"Error executing LLM task with context document: {task_error}")
                        # Fall back to searching all documents
                
                # If we're here, context document wasn't relevant to this query
                logger.info("Context document not relevant to query, falling back to all documents")
                print("Context document not relevant to query, falling back to all documents")
                await self.send_message("Librarian is expanding the search to all documents...")
            else:
                await self.send_message("Librarian is preparing to search...")
            
            # --- Continue with standard search across all documents ---
            # Get user-specific file DB interface AND vectorizer
            user_specific_db = FileDBInterface(user_id=user_id)
            vectorizer = FileVectorizer(user_id=user_id)
            
            # --- Step 2: Get all file metadata for the user ---
            await self.send_message("Librarian is analyzing your files...")
            
            # Load file metadata to get access to full text content
            metadata_file_path = f"data/files/{user_id}/file_metadata.json"
            
            try:
                if os.path.exists(metadata_file_path):
                    with open(metadata_file_path, 'r') as f:
                        all_files_metadata = json.load(f)
                    logger.info(f"Loaded metadata for {len(all_files_metadata)} files")
                else:
                    logger.warning(f"Metadata file not found: {metadata_file_path}")
                    all_files_metadata = []
            except Exception as e:
                logger.error(f"Error loading file metadata: {e}")
                all_files_metadata = []
            
            if not all_files_metadata:
                await self.send_message("Librarian couldn't find any files to search.")
                return self.format_response("I couldn't find any files in your library to search through.")
            
            # --- Step 3: Find the most relevant file using hybrid search ---
            try:
                # Hybrid approach: Combine semantic search with direct keyword matching
                
                # Initialize variables
                do_semantic_search = False
                most_relevant_file_name = None
                most_relevant_file_score = 0
                
                # 1. Direct keyword matching first (high precision)
                query_terms = [term.lower() for term in query.split() if len(term) > 3]
                keyword_match_scores = {}
                
                print(f"Searching for query terms: {query_terms}")
                
                # Check each file for presence of query terms
                for file_data in all_files_metadata:
                    file_name = file_data.get('file_name', '')
                    text_content = file_data.get('text_content', '').lower()
                    
                    # Count exact matches of query terms in document
                    match_count = sum(1 for term in query_terms if term in text_content)
                    match_percentage = match_count / len(query_terms) if query_terms else 0
                    
                    # Also check filename for matches
                    filename_matches = sum(1 for term in query_terms if term in file_name.lower())
                    
                    # Combined score with higher weight for filename matches
                    keyword_score = match_count + (filename_matches * 2)
                    
                    print(f"File '{file_name}' contains {match_count}/{len(query_terms)} query terms, {filename_matches} in filename")
                    keyword_match_scores[file_name] = keyword_score
                
                # Find files with keyword matches
                keyword_matches = {file_name: score for file_name, score in keyword_match_scores.items() if score > 0}
                
                # 2. If we have strong keyword matches, prioritize those files
                if keyword_matches:
                    print(f"Found keyword matches in {len(keyword_matches)} files")
                    # Sort by keyword match score (higher is better)
                    ranked_by_keywords = sorted(keyword_matches.items(), key=lambda x: x[1], reverse=True)
                    best_keyword_match = ranked_by_keywords[0][0]
                    best_keyword_score = ranked_by_keywords[0][1]
                    
                    # If we have a strong keyword match, use it directly
                    if best_keyword_score >= 2:  # At least 2 term matches or a filename match
                        most_relevant_file_name = best_keyword_match
                        print(f"Selected file based on strong keyword matches: {most_relevant_file_name}")
                        
                        # Skip the semantic search step
                        most_relevant_file_score = 1.0  # High confidence score
                    else:
                        # Otherwise, proceed with semantic search but give bonus to keyword matches
                        print(f"Proceeding with semantic search with keyword match bonus")
                        do_semantic_search = True
                else:
                    print(f"No keyword matches found, falling back to semantic search")
                    do_semantic_search = True
                
                # 3. Semantic search as fallback or refinement
                if not keyword_matches or do_semantic_search:
                    # Get semantic search results
                    search_results = vectorizer.search(query, limit=len(all_files_metadata) * 3)
                    
                    if not search_results:
                        await self.send_message("Librarian couldn't find relevant information.")
                        return self.format_response("I wasn't able to find information relevant to your query in your files.")
                    
                    # Create a score mapping for each file
                    file_relevance_scores = {}
                    best_distances_per_file = {}
                    
                    # Find the best (lowest) distance for each file first
                    for result in search_results:
                        file_name = result.get('file_name', '')
                        if not file_name:
                            continue
                            
                        distance = result.get('distance', 1000.0)
                        
                        # Track the lowest distance for each file
                        if file_name not in best_distances_per_file or distance < best_distances_per_file[file_name]:
                            best_distances_per_file[file_name] = distance
                    
                    # Find overall best distance across all files for normalization
                    if best_distances_per_file:
                        best_overall_distance = min(best_distances_per_file.values())
                        print(f"Best overall distance: {best_overall_distance}")
                    else:
                        best_overall_distance = 1.0  # Default if no distances available
                    
                    # Process each file using the best matching chunk and normalized score
                    for file_name, best_distance in best_distances_per_file.items():
                        # Normalize the score relative to the best match across all files
                        # This creates much stronger differentiation between relevance scores
                        normalized_score = best_overall_distance / best_distance
                        
                        # Apply keyword match bonus if available
                        keyword_bonus = 1.0
                        if file_name in keyword_matches:
                            # Scale bonus based on match strength
                            keyword_bonus = 1.0 + (keyword_matches[file_name] * 0.5)
                            print(f"Applied keyword bonus of {keyword_bonus}x to {file_name}")
                        
                        # Store the final score
                        file_relevance_scores[file_name] = {
                            'best_distance': best_distance,
                            'normalized_score': normalized_score * keyword_bonus,
                            'keyword_matches': keyword_matches.get(file_name, 0)
                        }
                    
                    # Sort files by normalized score (higher is better)
                    ranked_files = sorted(
                        file_relevance_scores.items(),
                        key=lambda x: x[1]['normalized_score'],
                        reverse=True
                    )
                    
                    # Debug info about file relevance
                    for rank, (file_name, data) in enumerate(ranked_files, 1):
                        print(f"Rank {rank}: {file_name} - Score: {data['normalized_score']:.4f}, Best Distance: {data['best_distance']:.2f}, Keywords: {data['keyword_matches']}")
                    
                    # Select the most relevant file
                    if ranked_files:
                        most_relevant_file_name = ranked_files[0][0]
                        most_relevant_file_score = ranked_files[0][1]['normalized_score']
                    
                    # Print metadata info for all files
                    print(f"File metadata found: {len(all_files_metadata)}")
                    for meta in all_files_metadata:
                        file_name = meta.get('file_name', 'Unknown')
                        vector_count = len(meta.get('related_vectors', []))
                        file_size = meta.get('file_size', 0)
                        print(f"File: {file_name}, Size: {file_size}, Vector count: {vector_count}")
            except Exception as search_error:
                logger.error(f"Error during search: {search_error}", exc_info=True)
                await self.send_message("Librarian encountered an issue during the search.")
                return self.format_response("I encountered an error while searching through your files.")
            
            # --- Step 4: Get and process the content of the selected file ---
            if not most_relevant_file_name:
                await self.send_message("Librarian couldn't identify a relevant file.")
                return self.format_response("I wasn't able to find information relevant to your query in your files.")
                
            # Find the metadata for the selected file
            selected_file_metadata = None
            for file_data in all_files_metadata:
                if file_data.get('file_name') == most_relevant_file_name:
                    selected_file_metadata = file_data
                    break
            
            if not selected_file_metadata:
                logger.error(f"Could not find metadata for file: {most_relevant_file_name}")
                await self.send_message("Librarian couldn't access the file content.")
                return self.format_response("I found a relevant file but couldn't access its content.")
            
            # Process the file content
            full_text_content = selected_file_metadata.get('text_content', '')
            
            # Estimate token count (rough approximation: ~4 chars per token)
            estimated_tokens = len(full_text_content) / 4
            token_threshold = 4000  # Slightly under 4096 to leave room for other prompt components
            
            # Determine whether to use full content or chunks
            use_full_content = estimated_tokens <= token_threshold
            
            if use_full_content:
                # Use the entire document content
                logger.info(f"Using full content of file (estimated {estimated_tokens:.0f} tokens)")
                await self.send_message(f"Librarian found a relevant document: '{most_relevant_file_name}'")
                
                # Prepare context with the full content
                file_context = f"Full content of file '{most_relevant_file_name}':\n\n{full_text_content}"
                
            else:
                # For larger documents, use the most relevant chunks
                logger.info(f"Using chunks for large file (estimated {estimated_tokens:.0f} tokens)")
                await self.send_message(f"Librarian found relevant information in '{most_relevant_file_name}'")
                
                # Get the most relevant chunks from this file
                all_chunks = vectorizer.search(query, limit=50)  # Get a good number of results
                
                # Filter to only chunks from the selected file
                file_chunks = [chunk for chunk in all_chunks if chunk.get('file_name', '') == most_relevant_file_name]
                
                # Sort by relevance (distance) and take the top chunks (up to token threshold)
                file_chunks.sort(key=lambda x: x.get('distance', 1000.0))
                
                # Build context from chunks
                file_context = f"Relevant information from file '{most_relevant_file_name}':\n\n"
                
                # Track token count
                current_token_estimate = len(file_context) / 4
                chunk_count = 0
                
                for chunk in file_chunks:
                    chunk_text = chunk.get('chunk_text', '').strip()
                    chunk_token_estimate = len(chunk_text) / 4
                    
                    # Add chunk if it fits within token threshold
                    if current_token_estimate + chunk_token_estimate <= token_threshold:
                        file_context += f"   \"{chunk_text}\"\n\n"
                        current_token_estimate += chunk_token_estimate
                        chunk_count += 1
                    else:
                        break
                
                logger.info(f"Using {chunk_count} chunks with approximately {current_token_estimate:.0f} tokens")
            
            # --- Step 5: Build LLM prompt and generate response ---
            description = f"""
                USER QUERY:

                {query}

                _________________________________________________________________________________________

                RELEVANT INFORMATION FROM USER'S FILES:

                {file_context}

                _________________________________________________________________________________________

                INSTRUCTIONS TO PERFORM THE TASK:

                1.  **Your Role:** You are Librarian, an AI assistant specialized in retrieving and synthesizing information *exclusively* from the user's documents provided above in the 'RELEVANT INFORMATION FROM USER'S FILES' section.
                2.  **Analyze:** Carefully read the USER QUERY and the provided RELEVANT INFORMATION FROM USER'S FILES to find information relevant to the query. 
                3.  **No answer found:** If no relevant information is found to answer the query, just let the user know by saying something like: "I couldn't find the information you were looking for. Try asking that differently." and nothing else.
                3.  **Answer Source:** Base your answer *strictly* and *only* on the information presented in the RELEVANT INFORMATION FROM USER'S FILES. Do **NOT** use any external knowledge or make assumptions beyond the provided text.
                4.  **Synthesize:** If multiple text passages from the same source document provide relevant information, combine them into a single, coherent, and concise answer. 
                5.  **Acknowledge Limits:** If the provided information only partially answers the query, state what you found and clearly mention what information is missing or couldn't be confirmed from the context.
                6.  **No Invention / Handling Absence of Information:** If the answer is **not present** in the provided context, DO NOT invent information. You MUST respond by stating that you couldn't find the relevant information in the provided files. Use phrasing like: "I couldn't find information about that in the files I searched." or "The provided documents don't seem to contain details about [topic of the query]."
                7.  **Tone & Style:** Be helpful, factual, and concise. Speak in the first person ("I found...", "It seems..."). Address the user directly but maintain a professional and informative tone.
                8.  **Formatting:** Respond in plain text. Do not use markdown code. 
                9.  **Final Output:** Your final output should *only* be the direct response to the user, fulfilling their query based on the constraints above.

                Now, answer the user's query based on the instructions provided.
            """

            # Create and execute the task
            task = Task(
                description=description,
                expected_output="A concise answer synthesized exclusively from the provided file content, directly addressing the user's query, or a statement indicating the information wasn't found in the provided context.",
                agent=self.agent
            )

            await self.send_message("Librarian is formulating the response...")
            
            # Execute the task with the agent
            loop = asyncio.get_event_loop()
            try:
                response = await loop.run_in_executor(None, self.agent.execute_task, task)
                await self.send_message("Librarian has prepared the response.")
                
                # Update document context for future queries
                self.set_document_context(user_id, most_relevant_file_name)
                
                # Return response with document context
                return self.format_response(response, context_document=most_relevant_file_name)
            except Exception as task_exec_error:
                logger.error(f"Error executing LLM task: {task_exec_error}", exc_info=True)
                await self.send_message("Librarian encountered an issue while formulating the response.")
                return self.format_response("I apologize, but I encountered an error while trying to process your request based on your files.")
            
        except Exception as e:
            # Catch any unexpected errors during the process
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Unhandled error in Librarian agent: {e}", exc_info=True)
            print(f"Error in Librarian agent: {e}")
            print(traceback.format_exc())
            await self.send_message("Librarian encountered an unexpected error.")
            return self.format_response("I encountered an unexpected error while trying to answer your query using your files.")

    async def _search_specific_document(self, query: str, user_id: str, document_name: str) -> Optional[Dict[str, Any]]:
        """Search specifically within a single document.
        
        Args:
            query: User query
            user_id: User ID
            document_name: Name of the document to search within
            
        Returns:
            Dictionary with search results if found, None if no relevant results
        """
        try:
            # Get vectorizer and file DB
            vectorizer = FileVectorizer(user_id=user_id)
            
            # Load metadata
            metadata_file_path = f"data/files/{user_id}/file_metadata.json"
            if not os.path.exists(metadata_file_path):
                print(f"Metadata file not found for context document search: {metadata_file_path}")
                return None
                
            with open(metadata_file_path, 'r') as f:
                all_files_metadata = json.load(f)
            
            # Find the specific document
            document_metadata = None
            for file_data in all_files_metadata:
                if file_data.get('file_name') == document_name:
                    document_metadata = file_data
                    break
            
            if not document_metadata:
                print(f"Context document not found in metadata: {document_name}")
                return None
            
            # Get full text content
            full_text_content = document_metadata.get('text_content', '').lower()
            if not full_text_content:
                print(f"No text content in context document: {document_name}")
                return None
                
            # Check for query term matches in the document content
            query_terms = [term.lower() for term in query.split() if len(term) > 3]
            term_matches = sum(1 for term in query_terms if term in full_text_content)
            print(f"Context document contains {term_matches}/{len(query_terms)} query terms")
            
            # Calculate term match ratio - this will help determine if document is relevant
            term_match_ratio = term_matches / len(query_terms) if query_terms else 0
            print(f"Term match ratio: {term_match_ratio:.2f}")
            
            # Perform semantic search
            all_chunks = vectorizer.search(query, limit=50)
            
            # Filter to only chunks from this document
            document_chunks = [chunk for chunk in all_chunks if chunk.get('file_name', '') == document_name]
            
            # If no chunks from this document match the query, it may not be relevant
            if not document_chunks:
                print(f"No semantic matches found in context document")
                return None
            
            # Check best semantic match quality
            best_distance = 1000.0
            if document_chunks:
                best_distance = min(chunk.get('distance', 1000.0) for chunk in document_chunks)
                print(f"Best semantic match in context document has distance: {best_distance}")
                
                # More strict relevance criteria based on combination of factors:
                # 1. If distance is very high (poor match)
                # 2. AND term match ratio is low
                # Then this document likely isn't relevant to the query
                
                # Check for top chunks across all files to see if this document is truly the best match
                all_results_top_distances = [r.get('distance', 1000.0) for r in all_chunks[:5] if r.get('file_name', '') != document_name]
                other_file_has_better_match = False
                
                if all_results_top_distances:
                    best_other_distance = min(all_results_top_distances)
                    if best_other_distance < best_distance:
                        other_file_has_better_match = True
                        print(f"Another file has better semantic match: {best_other_distance} vs {best_distance}")
                
                # Enhanced relevance check combining multiple signals
                not_relevant = (
                    (best_distance > 300 and term_match_ratio < 0.3) or  # High distance and low term matches
                    (best_distance > 350) or  # Very high distance regardless of terms
                    (term_match_ratio == 0 and len(query_terms) >= 3) or  # No term matches with significant query
                    other_file_has_better_match  # Another file has a clearly better match
                )
                
                if not_relevant:
                    print(f"Context document seems unrelated to query - switching context")
                    return None
            
            # Prepare document content for LLM
            estimated_tokens = len(full_text_content) / 4
            token_threshold = 4000
            
            if estimated_tokens <= token_threshold:
                # Use full content for small documents
                file_context = f"Full content of file '{document_name}':\n\n{full_text_content}"
                print(f"Using full content of context document ({estimated_tokens:.0f} tokens)")
            else:
                # Use chunks for larger documents
                document_chunks.sort(key=lambda x: x.get('distance', 1000.0))
                
                file_context = f"Relevant information from file '{document_name}':\n\n"
                current_token_estimate = len(file_context) / 4
                chunk_count = 0
                
                for chunk in document_chunks:
                    chunk_text = chunk.get('chunk_text', '').strip()
                    chunk_token_estimate = len(chunk_text) / 4
                    
                    if current_token_estimate + chunk_token_estimate <= token_threshold:
                        file_context += f"   \"{chunk_text}\"\n\n"
                        current_token_estimate += chunk_token_estimate
                        chunk_count += 1
                    else:
                        break
                
                print(f"Using {chunk_count} chunks from context document ({current_token_estimate:.0f} tokens)")
            
            # Return the context and search results
            return {
                "document_name": document_name,
                "file_context": file_context,
                "relevance_score": 1.0 / (1.0 + best_distance) if document_chunks else 0.0
            }
            
        except Exception as e:
            print(f"Error in document-specific search: {e}")
            import traceback
            print(traceback.format_exc())
            return None

    def format_response(self, answer: str, context_document: Optional[str] = None) -> Dict[str, Any]:
        """
        Format a response in the standard format expected by the frontend,
        with optional document context information.
        
        Args:
            answer: The answer text from the agent.
            context_document: Optional name of the document used as context.
            
        Returns:
            Dictionary containing the formatted response.
        """
        # Get basic response structure from parent method
        response = super().format_response(answer)
        
        # Add document context if provided
        if context_document:
            print(f"Including context document in response: '{context_document}'")
            response["context_document"] = context_document
        
        return response