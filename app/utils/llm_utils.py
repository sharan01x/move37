#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilities for handling LLM responses.
"""

import json
import re
import requests
from typing import Dict, Any, Tuple, Optional, Union
from app.core.config import CHAT_API_URL


def extract_json_from_llm_response(response_text: str) -> str:
    """
    Extract valid JSON from an LLM response text that might include non-JSON content.
    
    This function attempts to find JSON content in a response that may include markdown,
    explanatory text, or other non-JSON content. It looks for common patterns like:
    - JSON enclosed in triple backticks (```json {...} ```)
    - JSON starting with { and ending with } 
    - JSON starting with [ and ending with ]
    
    Args:
        response_text: The text response from an LLM that may contain JSON.
        
    Returns:
        The extracted JSON string if found, otherwise the original text.
    """
    # First, check if the entire string is valid JSON (best case)
    try:
        json.loads(response_text)
        return response_text  # It's already valid JSON
    except json.JSONDecodeError:
        # Not valid JSON, try to extract it
        pass
    
    # Try finding JSON within triple backticks - markdown code blocks
    json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
    json_match = re.search(json_pattern, response_text)
    if json_match:
        try:
            json_str = json_match.group(1).strip()
            # Validate it's actual parseable JSON
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            # Not valid JSON despite being in code blocks, continue
            pass
    
    # Try finding JSON between curly braces - look for properly balanced braces
    json_text = ""
    open_count = 0
    close_count = 0
    recording = False
    
    for i, char in enumerate(response_text):
        if char == '{':
            open_count += 1
            if open_count == 1 and not recording:
                recording = True
                json_text = '{'
            elif recording:
                json_text += char
        elif char == '}':
            close_count += 1
            if recording:
                json_text += char
                if open_count == close_count:
                    # Try to parse this as JSON
                    try:
                        json.loads(json_text)
                        return json_text
                    except json.JSONDecodeError:
                        # Reset and keep looking
                        open_count = 0
                        close_count = 0
                        recording = False
                        json_text = ""
        elif recording:
            json_text += char
    
    # If nothing else works, try a more aggressive approach to find any JSON object
    # Look for patterns like {"key": value} anywhere in the text
    potential_jsons = re.findall(r'{[^{}]*}', response_text)
    for potential in potential_jsons:
        try:
            # Only accept if it's truly valid JSON
            parsed = json.loads(potential)
            if isinstance(parsed, dict) and len(parsed) > 0:
                return potential
        except json.JSONDecodeError:
            continue
    
    # Last resort: check if there's any JSON-like content and try to clean it
    if '{' in response_text and '}' in response_text:
        # Try to extract the text between the first { and the last }
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        
        if start < end:
            potential_json = response_text[start:end]
            try:
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                # Try to fix common issues
                potential_json = potential_json.replace("'", '"')  # Replace single quotes with double quotes
                potential_json = re.sub(r'(\w+):', r'"\1":', potential_json)  # Add quotes to keys
                
                try:
                    json.loads(potential_json)
                    return potential_json
                except json.JSONDecodeError:
                    pass
    
    # If all extraction attempts fail, return the original text
    return response_text


def parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from a response string with robust error handling and cleanup.
    
    Args:
        response_text: Text that might contain JSON.
        
    Returns:
        Parsed JSON dictionary or None if parsing fails.
    """
    # First try extracting JSON if the response isn't already pure JSON
    cleaned_text = extract_json_from_llm_response(response_text)
    
    # Try parsing the cleaned text
    try:
        result = json.loads(cleaned_text)
        # Only return if it's a dictionary or can be converted to one
        if isinstance(result, dict):
            return result
        elif isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
            # If we got a list of dictionaries, return the first one
            return result[0]
        elif isinstance(result, list) and len(result) > 0:
            # If we just got a list, convert it to a dict
            return {"items": result}
        elif isinstance(result, (str, int, float, bool)):
            # For primitive types, wrap in a dict
            return {"value": result}
        else:
            return None
    except (json.JSONDecodeError, TypeError) as e:
        # If JSON parsing failed, try additional cleanup steps
        try:
            # Try replacing single quotes with double quotes (common error)
            if "'" in cleaned_text and '"' not in cleaned_text:
                cleaned_text = cleaned_text.replace("'", '"')
                result = json.loads(cleaned_text)
                return result if isinstance(result, dict) else {"value": result}
            
            # Try fixing unquoted keys (another common error)
            if re.search(r'{\s*\w+:', cleaned_text):
                cleaned_text = re.sub(r'(\w+):', r'"\1":', cleaned_text)
                result = json.loads(cleaned_text)
                return result if isinstance(result, dict) else {"value": result}
            
            # Try handling trailing commas (another common error)
            if re.search(r',\s*[}\]]', cleaned_text):
                cleaned_text = re.sub(r',(\s*[}\]])', r'\1', cleaned_text)
                result = json.loads(cleaned_text)
                return result if isinstance(result, dict) else {"value": result}
                
            # If no specific cleanup worked, log the error and return None
            print(f"Failed to parse JSON after cleanup: {str(e)}")
            return None
            
        except (json.JSONDecodeError, TypeError) as e2:
            # Log the error for debugging
            print(f"Failed to parse JSON after all cleanup attempts: {str(e2)}")
            return None


def extract_score_from_response(response_text: str, 
                               default_score: Union[int, float] = 0,
                               min_value: Union[int, float] = 0,
                               max_value: Union[int, float] = 100) -> Union[int, float]:
    """
    Extract a numerical score from a text response using regex.
    
    Args:
        response_text: The text to extract score from
        default_score: Default score if no score is found
        min_value: Minimum allowed score
        max_value: Maximum allowed score
        
    Returns:
        The extracted score value
    """
    # Look for "Score: X" pattern in the response
    score_match = re.search(r'[Ss]core:?\s*(\d+(?:\.\d+)?)', response_text)
    if score_match:
        score_str = score_match.group(1)
    else:
        # Try to find any number in the text that could be a score
        number_match = re.search(r'\b(\d+(?:\.\d+)?)\b', response_text)
        if number_match:
            number = float(number_match.group(1))
            if min_value <= number <= max_value:
                score_str = str(number)
            else:
                score_str = str(default_score)
        else:
            score_str = str(default_score)
    
    # Convert to number and ensure it's within range
    try:
        if '.' in score_str:
            score = float(score_str)
        else:
            score = int(score_str)
        return max(min_value, min(max_value, score))
    except (ValueError, TypeError):
        return default_score


def extract_reasoning_from_response(response_text: str, default_reason: str = "No reasoning provided") -> str:
    """
    Extract reasoning text from an LLM response.
    
    Args:
        response_text: The text to extract reasoning from
        default_reason: Default reason if no reason is found
        
    Returns:
        The extracted reasoning text
    """
    # Look for "Reasoning: X" pattern in the response
    reasoning_match = re.search(r'[Rr]easoning:?\s*(.*?)(?=$|\n\n)', response_text, re.DOTALL)
    if reasoning_match:
        return reasoning_match.group(1).strip()
    
    # If no specific reasoning pattern, use the whole response minus any score mentions
    score_pattern = re.compile(r'[Ss]core:?\s*\d+(?:\.\d+)?')
    clean_text = re.sub(score_pattern, '', response_text).strip()
    return clean_text if clean_text else default_reason


def sanitize_non_ascii(text: str) -> str:
    """
    Sanitizes text for JSON compatibility while preserving valid Unicode characters.
    This function ensures the text can be safely encoded in JSON while keeping readable
    Unicode characters intact. It only removes or replaces:
    - Control characters (U+0000 through U+001F, except for whitespace)
    - Non-printable characters
    - Other characters that could cause JSON parsing issues
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text safe for JSON encoding while preserving valid Unicode
    """
    if not text:
        return text
    
    # Define valid whitespace characters in JSON
    json_whitespace = {' ', '\n', '\r', '\t'}
    
    # Process each character
    return ''.join(
        c if (c.isprintable() or c in json_whitespace) else ' '
        for c in text
    )


def standardize_response_format(response_data: dict) -> dict:
    """
    Standardize different response formats to ensure compatibility between agents.
    
    Args:
        response_data: The response data to standardize
        
    Returns:
        A standardized dictionary with consistent structure
    """
    standardized = {
        "vector_results": [],
        "entity_results": []
    }
    
    # Handle the case where response has 'information' key
    if "information" in response_data:
        info_items = response_data["information"]
        
        # Convert information items to entity_results
        for item in info_items:
            if "entity" in item and "description" in item:
                entity_result = {
                    "entity": item["entity"],
                    "context": item["description"],
                    "id": f"info-{hash(item['entity'] + item['description']) & 0xFFFFFFFF}",
                    "distance": 0.0
                }
                standardized["entity_results"].append(entity_result)
            elif "entity" in item and "context" in item:
                standardized["entity_results"].append(item)
            elif "description" in item:
                # Create a generic entity result from description
                entity_result = {
                    "entity": "information",
                    "context": item["description"],
                    "id": f"info-{hash(item['description']) & 0xFFFFFFFF}",
                    "distance": 0.0
                }
                standardized["entity_results"].append(entity_result)
    
    # Copy original vector_results and entity_results if present
    if "vector_results" in response_data:
        standardized["vector_results"] = response_data["vector_results"]
    elif "query_results" in response_data:
        standardized["vector_results"] = response_data["query_results"]
    
    if "entity_results" in response_data:
        standardized["entity_results"] = response_data["entity_results"]
    elif "entities" in response_data:
        standardized["entity_results"] = response_data["entities"]
    
    # Preserve other useful fields from the original response
    for key in ["query", "user_id"]:
        if key in response_data:
            standardized[key] = response_data[key]
    
    return standardized
