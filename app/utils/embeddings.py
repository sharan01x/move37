#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilities for handling embeddings.
"""

import requests
from typing import List
from functools import lru_cache

from app.core.config import (
    EMBEDDING_MODEL,
    EMBEDDING_MODEL_DIMENSIONS,
    EMBEDDING_API_URL
)

@lru_cache(maxsize=1)
def get_embeddings_model():
    """
    Get embeddings using the LLM API.
    """
    class EmbeddingsModel:
        def embed_query(self, text: str) -> List[float]:
            try:
                response = requests.post(
                    EMBEDDING_API_URL,
                    json={"model": EMBEDDING_MODEL, "prompt": text}
                )
                response.raise_for_status()
                return response.json()["embedding"]
            except Exception as e:
                print(f"Error getting embeddings: {e}")
                # Return a zero vector of the correct dimension as fallback
                return [0.0] * EMBEDDING_MODEL_DIMENSIONS
    
    return EmbeddingsModel()

def get_embedding(text: str) -> List[float]:
    """
    Get embedding for a text string.
    
    Args:
        text: The text to get embeddings for.
        
    Returns:
        List of embedding values.
    """
    model = get_embeddings_model()
    return model.embed_query(text) 