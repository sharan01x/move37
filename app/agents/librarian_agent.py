#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Librarian agent for the Move 37 application.
Specializes in answering queries related to contents of files uploaded by the user.
"""

from typing import Dict, Any, List, Optional, Callable
from crewai import Task
import asyncio

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
        # We'll create user-specific instances as needed in the methods
    
    async def answer_query_async(self, query: str, user_id: str, message_callback: Optional[Callable] = None) -> str:
        """Answer a query asynchronously."""
        try:
            # Set message callback
            self.set_message_callback(message_callback)
            
            await self.send_message("Librarian is preparing to search...") # Added init message

            # Get user-specific file DB interface AND vectorizer
            user_specific_db = FileDBInterface(user_id=user_id)
            vectorizer = FileVectorizer(user_id=user_id)

            # Log the search attempt
            import logging
            from datetime import datetime # Ensure datetime is imported
            logger = logging.getLogger(__name__)
            logger.info(f"Librarian agent initiated for user '{user_id}' with query: '{query}'")

            # --- Semantic Search for Relevant File Chunks ---
            await self.send_message("Librarian is searching through your files...")
            try:
                relevant_chunks = vectorizer.search(query, limit=100) # THIS IS IMPORTANT -- KEEP THE NUMBER HIGH FIRST
                logger.info(f"Semantic search found {len(relevant_chunks)} initial relevant chunks.")
            except Exception as search_error:
                logger.error(f"Error during initial semantic search for user '{user_id}': {search_error}")
                relevant_chunks = []
                await self.send_message("Librarian encountered an issue during the search.")

            # --- Prepare Context for LLM (using only initial search results) ---
            file_context = ""
            if relevant_chunks:
                await self.send_message("Librarian is analyzing the findings...")
                logger.info(f"Formatting {len(relevant_chunks)} chunks for context.")
                # Sort chunks primarily by distance (ascending), secondarily by recency (descending)
                relevant_chunks.sort(
                    key=lambda x: (
                        x.get("distance", 1.0), # Lower distance is better
                        -1 * (datetime.fromisoformat(x.get("upload_date", "1970-01-01T00:00:00").split('.')[0]).timestamp()
                             if x.get("upload_date") else 0) # Newer is better
                    )
                )

                # Limit context size (e.g., top 10 most relevant chunks) -- THIS IS IMPORTANT - KEEP THE NUMBER LOW TO AVOID DUPLICATES
                max_chunks_for_context = 10
                context_chunks = relevant_chunks[:max_chunks_for_context]
                logger.info(f"Using top {len(context_chunks)} chunks for LLM context.")

                file_context = "Here is potentially relevant information extracted from the user's files:\n\n"
                for i, chunk in enumerate(context_chunks, 1):
                    upload_date_str = "unknown date"
                    try:
                        upload_date = chunk.get('upload_date')
                        if upload_date:
                            # Handle potential microseconds '.f' which fromisoformat might not like depending on Python version / format variations
                             upload_date_cleaned = upload_date.split('.')[0]
                             upload_date_str = datetime.fromisoformat(upload_date_cleaned).strftime("%B %d, %Y")
                    except (ValueError, KeyError, AttributeError) as date_err:
                         logger.warning(f"Could not parse date '{chunk.get('upload_date')}': {date_err}")

                    file_name = chunk.get('file_name', 'Unknown File')
                    chunk_text_snippet = chunk.get('chunk_text', '').strip()

                    file_context += f"{i}. From file '{file_name}' (Uploaded: {upload_date_str}):\n"
                    # Use the full chunk text, adding quotes for clarity
                    file_context += f"   \"{chunk_text_snippet}\"\n\n"
            else:
                logger.info("No relevant file content found to provide as context.")
                file_context = "No specific information relevant to the query was found in the user's files after searching."
                await self.send_message("Librarian couldn't find relevant information in your files.")

            # --- Build LLM Prompt ---
            logger.debug("Building description for LLM task.")
            description = f"""
                USER QUERY:

                {query}

                _________________________________________________________________________________________

                RELEVANT INFORMATION FROM USER'S FILES:

                {file_context}

                _________________________________________________________________________________________

                INSTRUCTIONS TO PERFORM THE TASK:

                1.  **Your Role:** You are Librarian, an AI assistant specialized in retrieving and synthesizing information *exclusively* from the user's documents provided above in the 'RELEVANT INFORMATION FROM USER'S FILES' section.
                2.  **Analyze:** Carefully read the USER QUERY and the provided RELEVANT INFORMATION FROM USER'S FILES only if it is relevant to the query. IF no relevant information is found to answer the query, simply respond saying, "I wasn't able to find relevant information in your files."
                3.  **Answer Source:** Base your answer *strictly* and *only* on the information presented in the RELEVANT INFORMATION FROM USER'S FILES. Do **NOT** use any external knowledge or make assumptions beyond the provided text.
                4.  **Synthesize:** If multiple text passages from the same source document provide relevant information, combine them into a single, coherent, and concise answer. 
                5.  **Acknowledge Limits:** If the provided information only partially answers the query, state what you found and clearly mention what information is missing or couldn't be confirmed from the context.
                6.  **No Invention / Handling Absence of Information:** If the answer is **not present** in the provided context, DO NOT invent information. You MUST respond by stating that you couldn't find the relevant information in the provided files. Use phrasing like: "I couldn't find information about that in the files I searched." or "The provided documents don't seem to contain details about [topic of the query]."
                7.  **Citing Sources:** Briefly mention the source file when relevant, but naturally. Example: "In the document '{{file_name}}', it mentions..." or "Based on your file '{{file_name}}'..." Avoid technical terms like "chunks", "snippets", "database", "vector search". Refer to the information source as "your files" or "your documents".
                8.  **Tone & Style:** Be helpful, factual, and concise. Speak in the first person ("I found...", "It seems..."). Address the user directly but maintain a professional and informative tone.
                9.  **Formatting:** Respond in plain text. Do not use markdown code. 
                10. **Final Output:** Your final output should *only* be the direct response to the user, fulfilling their query based on the constraints above.

            """

            # --- Execute LLM Task ---
            logger.info("Creating and executing LLM task.")
            task = Task(
                description=description,
                expected_output="A concise answer synthesized exclusively from the provided file content chunks, directly addressing the user's query, or a statement indicating the information wasn't found in the provided context.",
                agent=self.agent
            )

            await self.send_message("Librarian is formulating the response...")
            # Execute the task with the agent (using run_in_executor for potentially blocking calls)
            loop = asyncio.get_event_loop()
            try:
                response = await loop.run_in_executor(None, self.agent.execute_task, task)
                logger.info("LLM task executed successfully.")
                await self.send_message("Librarian has prepared the response.")
            except Exception as task_exec_error:
                logger.error(f"Error executing LLM task: {task_exec_error}")
                await self.send_message("Librarian encountered an issue while formulating the response.")
                # Provide a fallback error message to the user
                return self.format_response("I apologize, but I encountered an error while trying to process your request based on your files.")


            return self.format_response(response)

        except Exception as e:
            # Catch any unexpected errors during the process
            logger.error(f"Unhandled error in Librarian agent's answer_query_async: {e}", exc_info=True) # Log traceback
            await self.send_message("Librarian encountered an unexpected error.")
            # Provide a generic error message
            return self.format_response("I encountered an unexpected error while trying to answer your query using your files.")

        except Exception as e:
            print(f"Error in Librarian agent: {e}")
            return self.format_response("I encountered an error while searching for information.") 