#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Text chunking utilities for the LifeScribe application.
"""

from typing import List, Dict, Any, Callable
import re
import spacy
import numpy as np
from scipy.spatial.distance import cosine
import logging

logger = logging.getLogger(__name__)

# Load the spaCy model once when the module is loaded
# Ensure you have downloaded the model: python -m spacy download en_core_web_sm
# We still might need spaCy for the fallback or other utilities, keep the load attempt.
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.error("SpaCy model 'en_core_web_sm' not found. Please download it: python -m spacy download en_core_web_sm")
    nlp = None 

DEFAULT_SIMILARITY_THRESHOLD = 0.85 # Tunable parameter: Lower = more splits, larger chunks. Higher = fewer splits, smaller chunks.

class ChunkingUtil:
    """Utility for chunking text."""
    
    @staticmethod
    def _get_paragraphs_with_spans(text: str) -> List[Dict[str, Any]]:
        """Splits text into paragraphs based on double newlines and retains character spans."""
        paragraphs = []
        start_index = 0
        # Find paragraph breaks (two or more newlines potentially separated by whitespace)
        for match in re.finditer(r'\n\s*\n', text):
            end_index = match.start()
            para_text = text[start_index:end_index].strip()
            if para_text: # Only add non-empty paragraphs
                # Find the actual start/end within the original slice to account for stripping
                text_slice = text[start_index:end_index]
                actual_start = start_index + text_slice.find(para_text)
                actual_end = actual_start + len(para_text)
                paragraphs.append({"text": para_text, "start": actual_start, "end": actual_end})
            # Next paragraph starts after the match    
            start_index = match.end()
            
        # Add the last paragraph after the last match
        last_para_text = text[start_index:].strip()
        if last_para_text:
            text_slice = text[start_index:]
            actual_start = start_index + text_slice.find(last_para_text)
            actual_end = actual_start + len(last_para_text)
            paragraphs.append({"text": last_para_text, "start": actual_start, "end": actual_end})
            
        return paragraphs
        
    @staticmethod
    def semantic_chunk_text(
        text: str, 
        embedding_function: Callable[[str], np.ndarray],
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> List[Dict[str, Any]]:
        """
        Chunk text into semantically coherent pieces using sentence embeddings.
        
        Args:
            text: Text to chunk.
            embedding_function: Function to generate embeddings (e.g., get_embedding).
            similarity_threshold: Cosine similarity threshold to determine breakpoints. 
                                  Splits occur when similarity drops below this value.
                                  Value should be between 0 and 1. Default: 0.85.
            
        Returns:
            List of dictionaries containing the chunks and their metadata.
        """
        if not text or not text.strip():
            return []
            
        # We don't strictly need spaCy for paragraph splitting, but keep fallback logic
        # if not nlp:
        #      logger.warning("SpaCy model not loaded. Falling back to simple chunking.")
        #      # Fallback to the simple method if spaCy isn't available
        #      return ChunkingUtil.chunk_text(text) 
        
        text = text.strip()
        
        # 1. Split into paragraphs with spans
        paragraphs = ChunkingUtil._get_paragraphs_with_spans(text)
        
        if not paragraphs:
            return []

        if len(paragraphs) <= 1:
            # If only one paragraph or less, return the whole text as one chunk
            return [{
                'text': paragraphs[0]['text'],
                'start': paragraphs[0]['start'],
                'end': paragraphs[0]['end'],
                'chunk_index': 0
            }]
            
        logger.debug(f"Starting semantic chunking for text of length {len(text)} with {len(paragraphs)} paragraphs.")
        
        # 2. Get embeddings for all paragraphs
        try:
            paragraph_embeddings = [embedding_function(para['text']) for para in paragraphs]
            paragraph_embeddings = np.array(paragraph_embeddings)
        except Exception as e:
            logger.error(f"Error getting paragraph embeddings: {e}", exc_info=True)
            logger.warning("Failed to get paragraph embeddings. Falling back to simple chunking.")
            return ChunkingUtil.chunk_text(text)
            
        # 3. Calculate cosine similarities between adjacent paragraphs
        similarities = [1 - cosine(paragraph_embeddings[i], paragraph_embeddings[i+1]) 
                        for i in range(len(paragraph_embeddings) - 1)]
        
        logger.debug(f"Calculated {len(similarities)} paragraph similarities. Threshold: {similarity_threshold}")
        
        chunks = []
        current_chunk_start_para_index = 0
        chunk_index = 0
        
        # 4. Identify split points and group paragraphs
        for i in range(len(similarities)):
            if similarities[i] < similarity_threshold:
                logger.debug(f"Split point detected after paragraph {i} (similarity: {similarities[i]:.4f})")
                # End of a chunk. Group paragraphs from current_chunk_start_para_index to i.
                chunk_paragraphs = paragraphs[current_chunk_start_para_index : i+1]
                
                # 5. Combine paragraph texts and calculate final chunk span
                chunk_text = "\n\n".join([para['text'] for para in chunk_paragraphs]) # Re-join with double newline
                start_char = chunk_paragraphs[0]['start']
                end_char = chunk_paragraphs[-1]['end']
                
                chunks.append({
                    'text': chunk_text,
                    'start': start_char,
                    'end': end_char,
                    'chunk_index': chunk_index
                })
                
                # Start the next chunk after this paragraph
                current_chunk_start_para_index = i + 1
                chunk_index += 1
                
        # 6. Add the last remaining chunk
        if current_chunk_start_para_index < len(paragraphs):
            chunk_paragraphs = paragraphs[current_chunk_start_para_index:]
            chunk_text = "\n\n".join([para['text'] for para in chunk_paragraphs]) # Re-join with double newline
            start_char = chunk_paragraphs[0]['start']
            end_char = chunk_paragraphs[-1]['end']
            
            chunks.append({
                'text': chunk_text,
                'start': start_char,
                'end': end_char,
                'chunk_index': chunk_index
            })
            
        logger.debug(f"Semantic chunking based on paragraphs resulted in {len(chunks)} chunks.")
        return chunks

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[Dict[str, Any]]:
        """
        Chunk text into smaller pieces.
        
        Args:
            text: Text to chunk.
            chunk_size: Size of each chunk in characters.
            overlap: Overlap between chunks in characters.
            
        Returns:
            List of dictionaries containing the chunks and their metadata.
        """
        # Clean the text
        text = text.strip()
        
        # If text is shorter than chunk_size, return it as a single chunk
        if len(text) <= chunk_size:
            return [{
                'text': text,
                'start': 0,
                'end': len(text),
                'chunk_index': 0
            }]
        
        # Split the text into sentences
        sentences = ChunkingUtil._split_into_sentences(text)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        last_end = 0
        chunk_index = 0
        
        for sentence in sentences:
            # If adding this sentence would exceed the chunk size
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                # Save the current chunk
                chunks.append({
                    'text': current_chunk,
                    'start': current_start,
                    'end': last_end,
                    'chunk_index': chunk_index
                })
                
                # Start a new chunk with overlap
                overlap_text = text[max(0, last_end - overlap):last_end]
                current_chunk = overlap_text + sentence
                current_start = max(0, last_end - overlap)
                chunk_index += 1
            else:
                # Add the sentence to the current chunk
                current_chunk += sentence
            
            last_end = text.find(sentence, last_end) + len(sentence)
        
        # Add the last chunk if there's any text left
        if current_chunk:
            chunks.append({
                'text': current_chunk,
                'start': current_start,
                'end': last_end,
                'chunk_index': chunk_index
            })
        
        return chunks
    
    @staticmethod
    def _split_into_sentences(text: str) -> List[str]:
        """
        Split text into sentences.
        
        Args:
            text: Text to split.
            
        Returns:
            List of sentences.
        """
        # Simple sentence splitting using regex
        # In a production application, you might want to use a more sophisticated approach
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', text)
        
        # Add the space back to the end of each sentence
        sentences = [s + " " if not s.endswith(" ") else s for s in sentences]
        
        return sentences
