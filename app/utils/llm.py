#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utility functions for interacting with LLMs.
"""

import json
import logging
import requests
from typing import Dict, Any, List, Optional, Union

from app.core.config import CHAT_API_URL

logger = logging.getLogger(__name__)

async def get_llm_response(
    provider: str,
    model: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 500,
    system_prompt: Optional[str] = None
) -> str:
    """
    Get a response from an LLM.
    
    Args:
        provider: LLM provider (e.g., "ollama", "openai").
        model: Model name.
        prompt: User prompt.
        temperature: Temperature for sampling.
        max_tokens: Maximum number of tokens to generate.
        system_prompt: Optional system prompt.
        
    Returns:
        The LLM response as a string.
    """
    try:
        if provider.lower() == "ollama":
            return await _get_ollama_response(model, prompt, temperature, max_tokens, system_prompt)
        else:
            logger.warning(f"Unsupported LLM provider: {provider}. Falling back to Ollama.")
            return await _get_ollama_response(model, prompt, temperature, max_tokens, system_prompt)
    except Exception as e:
        logger.error(f"Error getting LLM response: {e}")
        return f"Error: {str(e)}"

async def _get_ollama_response(
    model: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 500,
    system_prompt: Optional[str] = None
) -> str:
    """
    Get a response from Ollama.
    
    Args:
        model: Model name.
        prompt: User prompt.
        temperature: Temperature for sampling.
        max_tokens: Maximum number of tokens to generate.
        system_prompt: Optional system prompt.
        
    Returns:
        The Ollama response as a string.
    """
    # Prepare the messages
    messages = []
    
    # Add system prompt if provided
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    # Add user prompt
    messages.append({"role": "user", "content": prompt})
    
    # Prepare the payload
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens
        }
    }
    
    # Make the API call
    response = requests.post(CHAT_API_URL, json=payload)
    response.raise_for_status()
    
    # Extract the content from the response
    response_json = response.json()
    response_text = response_json.get("message", {}).get("content", "")
    
    if not response_text:
        # Try alternative response format if the above doesn't work
        response_text = response_json.get("response", "")
    
    return response_text 