#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Configuration settings for the Move 37 application.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in the same directory as this file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path, override=True)  # override=True ensures all variables are loaded

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Data directory
DATA_DIR = Path(BASE_DIR).parent / "data" 
os.makedirs(DATA_DIR, exist_ok=True)

# User data directory - primary storage for all user-specific data
USER_DATA_DIR = os.path.join(DATA_DIR, "user_data")
os.makedirs(USER_DATA_DIR, exist_ok=True)

# User facts database path - for storing extracted user information
USER_FACTS_DB_PATH = os.path.join(DATA_DIR, "user_facts")
os.makedirs(USER_FACTS_DB_PATH, exist_ok=True)

# File Upload Settings
FILE_DB_PATH = os.path.join(DATA_DIR, "files")  # Path for file database
os.makedirs(FILE_DB_PATH, exist_ok=True)

# Social media temporary files
SOCIAL_MEDIA_TEMP_PATH = os.path.join(DATA_DIR, "social_media", "temporary")  # Path for temporary social media uploads
os.makedirs(SOCIAL_MEDIA_TEMP_PATH, exist_ok=True)

# Vector database type used throughout the application
VECTOR_DB_TYPE = "faiss"  # Type of vector database to use

# Conversations Vector Database Path
CONVERSATIONS_VECTOR_DB_PATH = os.path.join(DATA_DIR, "conversations")  # Path for conversations vector database
os.makedirs(CONVERSATIONS_VECTOR_DB_PATH, exist_ok=True)

# API settings
API_HOST = "0.0.0.0"
API_PORT = int(os.environ.get("API_PORT", 8000))

# Agent-specific LLM settings
# First Responder Agent
FIRST_RESPONDER_LLM_PROVIDER = "ollama"
FIRST_RESPONDER_LLM_MODEL = "qwen2.5:latest"  # A capable model for factual knowledge

# Number Ninja Agent
NUMBER_NINJA_LLM_PROVIDER = "ollama"
NUMBER_NINJA_LLM_MODEL = "phi4-mini:latest"  # Mathematics specialist model

# Context Builder Agent
CONTEXT_BUILDER_LLM_PROVIDER = "ollama"
CONTEXT_BUILDER_LLM_MODEL = "qwen2.5:latest"  # A capable model for context analysis

# Conductor Agent
CONDUCTOR_LLM_PROVIDER = "ollama"
CONDUCTOR_LLM_MODEL = "qwen2.5:latest"

# Transcriber Agent
TRANSCRIBER_LLM_PROVIDER = "ollama"
TRANSCRIBER_LLM_MODEL = "qwen2.5:latest"

# Recorder Agent
RECORDER_LLM_PROVIDER = "ollama"
RECORDER_LLM_MODEL = "qwen2.5:latest"

# User Fact Extractor Agent
USER_FACT_EXTRACTOR_LLM_PROVIDER = "ollama"
USER_FACT_EXTRACTOR_LLM_MODEL = "qwen2.5:latest"

# Persephone Agent
PERSEPHONE_LLM_PROVIDER = "ollama"
PERSEPHONE_LLM_MODEL = "qwen3:latest"

# Librarian Agent
LIBRARIAN_LLM_PROVIDER = "ollama"
LIBRARIAN_LLM_MODEL = "gemma3:4b"

# Social Media Agent
BUTTERFLY_LLM_PROVIDER = "ollama"
BUTTERFLY_LLM_MODEL = "phi4-mini:latest"

# Recall Agent (MCP-based)
THINKER_LLM_PROVIDER = "ollama"
THINKER_LLM_MODEL = "qwen3:latest"  # Using the most capable model for tool use

# Fast Processing Model
FAST_PROCESSING_LLM_PROVIDER = "ollama"
FAST_PROCESSING_LLM_MODEL = "phi4-mini:latest"

# For OpenAI (if used)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# LLM Settings
CHAT_API_URL = os.environ.get("OLLAMA_CHAT_API_URL", "http://localhost:11434/api/chat")
EMBEDDING_API_URL = os.environ.get("OLLAMA_EMBEDDING_API_URL", "http://localhost:11434/api/embeddings")
EMBEDDING_MODEL = os.environ.get("OLLAMA_EMBEDDING_MODEL", "mxbai-embed-large")
EMBEDDING_MODEL_DIMENSIONS = 1024

# Speech recognition settings
TRANSCRIPTION_SERVICE = "local"  # can be: "local", "google", "assemblyai", etc.
ASSEMBLYAI_API_KEY = os.environ.get("ASSEMBLYAI_API_KEY", "")
GOOGLE_SPEECH_API_KEY = os.environ.get("GOOGLE_SPEECH_API_KEY", "")

# File settings
FILE_CHUNK_SIZE = 1024 * 1024  # 1MB chunks for file processing
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_FILE_TYPES = [
    "text/plain",
    "text/markdown",
    "text/x-markdown",  # Some browsers use this MIME type for Markdown files
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "application/json"
]

# MCP Settings
MCP_SERVER_HOST = os.environ.get("MCP_SERVER_HOST", "localhost")
MCP_SERVER_PORT = int(os.environ.get("MCP_SERVER_PORT", 7777))

# Browser settings
BROWSER_LLM_MODEL = "qwen2.5:latest"
BROWSER_BINARY_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"  # Path to the browser binary
os.environ["ANONYMIZED_TELEMETRY"] = "false"

# Locale settings
USER_LOCATION = "Europe/Madrid"
USER_LANGUAGE = "en-gb"
