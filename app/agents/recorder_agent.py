#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Recorder agent for the Move 37 application.
"""

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_community.tools import Tool
import numpy as np

from app.agents.base_agent import BaseAgent
from app.utils.chunking import ChunkingUtil
from app.database.recorder_vector_db import RecorderVectorDBInterface
from app.core.config import USER_DATA_DIR, RECORDER_LLM_PROVIDER, RECORDER_LLM_MODEL


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder for datetime objects."""
    
    def default(self, obj):
        """Encode datetime objects as ISO format strings."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RecorderAgent(BaseAgent):
    """Recorder agent for the Move 37 application."""
    
    def __init__(self):
        """Initialize the Recorder agent."""
        # Initialize vector_db as None - it will be initialized per user
        self.vector_db = None
        
        # Define tools
        save_record_tool = Tool(
            name="save_record",
            func=self._save_record,
            description="Save a record to disk"
        )
        
        chunk_text_tool = Tool(
            name="chunk_text",
            func=self._chunk_text,
            description="Split text into chunks for storage"
        )
        
        store_chunk_tool = Tool(
            name="store_chunk",
            func=self._store_chunk,
            description="Store a text chunk in the vector database"
        )
        
        super().__init__(
            name="Recorder",
            description="I am an expert at recording and storing data. "
                        "I can save data packages, transcribe them, chunk them, "
                        "and store them in a vector database for easy retrieval.",
            role="Data Recorder",
            goal="Efficiently record and store data for future retrieval",
            tools=[save_record_tool, chunk_text_tool, store_chunk_tool],
            llm_provider=RECORDER_LLM_PROVIDER,
            llm_model=RECORDER_LLM_MODEL
        )
    
    def _ensure_vector_db(self, user_id: str):
        """
        Ensure the vector database is initialized for the given user.
        
        Args:
            user_id: The ID of the user whose data is being managed.
        """
        if not self.vector_db or self.vector_db.user_id != user_id:
            self.vector_db = RecorderVectorDBInterface(user_id=user_id)
    
    def _save_record(self, user_id: str, data_package: Dict[str, Any], transcription: Optional[str] = None) -> Dict[str, Any]:
        """
        Save a record to the user's account folder.
        
        Args:
            user_id: User ID.
            data_package: Data package to save.
            transcription: Transcription of the data package.
            
        Returns:
            Dictionary containing the record ID and path.
        """
        # Create a unique ID for the record
        record_id = str(uuid.uuid4())
        
        # Create the user's records directory
        user_records_dir = os.path.join(USER_DATA_DIR, user_id, "records")
        os.makedirs(user_records_dir, exist_ok=True)
        
        # Create the record directory
        record_dir = os.path.join(user_records_dir, record_id)
        os.makedirs(record_dir, exist_ok=True)
        
        # Save the data package
        data_package_path = os.path.join(record_dir, "data_package.json")
        
        # Convert bytes to base64 for JSON serialization
        data_package_json = data_package.copy()
        if data_package_json.get("voice_content") and isinstance(data_package_json["voice_content"], bytes):
            import base64
            data_package_json["voice_content"] = base64.b64encode(data_package_json["voice_content"]).decode('utf-8')
        if data_package_json.get("file_content") and isinstance(data_package_json["file_content"], bytes):
            import base64
            data_package_json["file_content"] = base64.b64encode(data_package_json["file_content"]).decode('utf-8')
        
        with open(data_package_path, 'w') as f:
            json.dump(data_package_json, f, cls=DateTimeEncoder)
        
        # Save the transcription if provided
        if transcription:
            transcription_path = os.path.join(record_dir, "transcription.txt")
            with open(transcription_path, 'w') as f:
                f.write(transcription)
        
        return {
            "record_id": record_id,
            "record_path": record_dir
        }
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[Dict[str, Any]]:
        """
        Chunk text into smaller pieces.
        
        Args:
            text: Text to chunk.
            chunk_size: Size of each chunk in characters.
            overlap: Overlap between chunks in characters.
            
        Returns:
            List of dictionaries containing the chunks and their metadata.
        """
        return ChunkingUtil.chunk_text(text, chunk_size, overlap)
    
    def _store_chunk(self, chunk: Dict[str, Any], record_id: str, user_id: str) -> Dict[str, Any]:
        """
        Store a chunk in the vector database.
        
        Args:
            chunk: The chunk to store.
            record_id: The record ID.
            user_id: The user ID.
            
        Returns:
            The result of storing the chunk.
        """
        # Ensure vector database is initialized for this user
        self._ensure_vector_db(user_id)
        
        # Use our own embedding function instead of langchain_huggingface
        from app.utils.embeddings import get_embedding
        
        # Create an embedding for the chunk
        embedding = get_embedding(chunk["text"])
        
        # Convert embedding to numpy array if it's a list
        if isinstance(embedding, list):
            embedding = np.array(embedding, dtype=np.float32)
        
        # Ensure the embedding is 2D
        if len(embedding.shape) == 1:
            embedding = embedding.reshape(1, -1)
        
        # Create metadata for the chunk
        chunk_metadata = {
            "text": chunk["text"],
            "start": chunk["start"],
            "end": chunk["end"],
            "chunk_index": chunk["chunk_index"],
            "record_id": record_id,
            "user_id": user_id
        }
        
        # Add the chunk to the vector database using the specialized method
        chunk_id = self.vector_db.add_recording(
            text=chunk["text"],
            embedding=embedding,
            metadata=chunk_metadata
        )
        
        return {
            "chunk_id": chunk_id,
            "metadata": chunk_metadata
        }
    
    def record(self, user_id: str, data_package: Dict[str, Any], transcription: Optional[str] = None) -> Dict[str, Any]:
        """
        Record a data package.
        
        Args:
            user_id: User ID.
            data_package: Data package to record.
            transcription: Transcription of the data package.
            
        Returns:
            Dictionary containing the record result.
        """
        # Ensure vector database is initialized for this user
        self._ensure_vector_db(user_id)
        
        # Save the record
        record_result = self._save_record(user_id, data_package, transcription)
        record_id = record_result["record_id"]
        
        # If there's a transcription, chunk it and store the chunks
        chunk_ids = []
        if transcription:
            chunks = self._chunk_text(transcription)
            
            for chunk in chunks:
                chunk_result = self._store_chunk(chunk, record_id, user_id)
                chunk_ids.append(chunk_result["chunk_id"])
        
        return {
            "record_id": record_id,
            "record_path": record_result["record_path"],
            "chunk_ids": chunk_ids,
            "chunk_count": len(chunk_ids)
        }
    
    def record_text(self, user_id: str, text: str, source: str = "User Input", metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Record text content.
        
        Args:
            user_id: User ID.
            text: Text content to record.
            source: Source of the text content.
            metadata: Additional metadata.
            
        Returns:
            Record ID.
        """
        # Initialize a user-specific vector database
        self._ensure_vector_db(user_id)
        
        # Create a data package
        data_package = {
            "user_id": user_id,
            "operation_type": "Record",
            "data_type": "text",
            "text_content": text,
            "timestamp": datetime.now(),
            "metadata": metadata or {},
            "source": source
        }
        
        # Record the data package
        record_result = self.record(user_id, data_package, text)
        
        return record_result["record_id"]
