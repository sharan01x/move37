import os
import requests
import json
from typing import Dict, List, Any, Optional, Union
import logging
import dotenv

from ..core.config import (
    VENICEAI_API_URL,
    WEB_SEARCH_LLM_MODEL
)

dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'app', '.env')
dotenv.load_dotenv(dotenv_path)

# Load environment variables
VENICEAI_API_KEY = os.getenv("VENICEAI_API_KEY")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_web(
    query: str,
    max_results: int = 1,
    enable_citations: bool = False,
    api_key: str = VENICEAI_API_KEY,
    api_url: str = VENICEAI_API_URL,
    model: str = WEB_SEARCH_LLM_MODEL
) -> Dict[str, Any]:
    """
    Perform a web search using VeniceAI.
    
    Args:
        query: The search query
        max_results: Maximum number of web results to consider (default: 3)
        enable_citations: Whether to include citations in the response
        api_key: VeniceAI API key (defaults to environment variable)
        api_url: VeniceAI API endpoint (defaults to config value)
        model: Model to use for the query (defaults to config value)
        
    Returns:
        Dict containing:
        - success: Boolean indicating if the request was successful
        - data: Dict containing:
            - search_results: List of response choices from the model
            - citations: List of web search citations if enabled
        - error: Error message if request failed
    """
    if not api_key:
        return {"error": "VENICEAI_API_KEY not configured", "success": False}
        
    # Construct the API request payload
    payload = {
        "frequency_penalty": 0,
        "n": 1,
        "presence_penalty": 0,
        "temperature": 0.3,
        "top_p": 1,
        "venice_parameters": {
            "include_venice_system_prompt": False,
            "enable_web_citations": enable_citations,
            "enable_web_search": "on",
            "max_search_results": max_results
        },
        "parallel_tool_calls": False,
        "messages": [
            {
                "content": "You are a helpful assistant that can browse the web to find information. You will answer the question as accurately and briefly as possible.",
                "role": "system",
                "name": "web-search-agent"
            },
            {
                "content": query,
                "role": "user"
            }
        ],
        "model": model
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept-Encoding": "",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Sending web search request for query: {query}")
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        # Parse the response
        response_data = response.json()
        
        # Extract the content directly from the first choice's message
        result = {
            "success": True,
            "data": {
                "results": response_data.get("choices", [{}])[0].get("message", {}).get("content", "No results found")
            }
        }
        
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return {
            "success": False,
            "error": f"API request failed: {str(e)}"
        }
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing API response: {str(e)}")
        return {
            "success": False,
            "error": f"Error parsing API response: {str(e)}"
        }
            
    