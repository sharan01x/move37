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

print(f"VENICEAI_API_URL: {VENICEAI_API_URL}")
print(f"WEB_SEARCH_LLM_MODEL: {WEB_SEARCH_LLM_MODEL}")

dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'app', '.env')
dotenv.load_dotenv(dotenv_path)

# Load environment variables
VENICEAI_API_KEY = os.getenv("VENICEAI_API_KEY")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSearchTool:
    """
    A tool that enables web search functionality using VeniceAI's API.
    This tool allows querying the web and returns results with citations.
    """

    def __init__(self):
        """
        Initialize the WebSearchTool with API key from environment variables.
        """
        self.api_key = VENICEAI_API_KEY
        if not self.api_key:
            logger.warning("VENICEAI_API_KEY environment variable not set")
            
        self.api_url = VENICEAI_API_URL
        self.default_model = WEB_SEARCH_LLM_MODEL

    def search(self, 
              query: str, 
              max_results: int = 3, 
              enable_citations: bool = True,
              temperature: float = 0.3,
              system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform a web search using VeniceAI.
        
        Args:
            query: The search query
            max_results: Maximum number of web results to consider (default: 3)
            enable_citations: Whether to include citations in the response
            temperature: Temperature parameter for response generation
            system_prompt: Custom system prompt (uses default if None)
            
        Returns:
            Dict containing search results with citations if enabled
        """
        if not self.api_key:
            return {"error": "VENICEAI_API_KEY not configured", "success": False}
            
        # Create default system prompt if none provided
        if not system_prompt:
            system_prompt = (
                f"You are a helpful web search assistant. "
                f"Search across a maximum of {max_results} websites to find accurate information. "
                f"Provide a clear, concise answer to the query. "
                f"{'Include citations to your sources.' if enable_citations else 'Do not include citations.'}"
            )
            
        # Construct the API request payload
        payload = {
            "frequency_penalty": 0,
            "n": 1,
            "presence_penalty": 0,
            "temperature": temperature,
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
                    "content": system_prompt,
                    "role": "system",
                    "name": "web-search-agent"
                },
                {
                    "content": query,
                    "role": "user"
                }
            ],
            "model": self.default_model
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept-Encoding": "",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Sending web search request for query: {query}")
            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            response_data = response.json()
            
            # Extract the relevant information from the response
            result = {
                "success": True,
                "query": query,
                "response": response_data["choices"][0]["message"]["content"],
                "model": response_data.get("model", self.default_model),
            }
            
            # Extract citations if available
            if enable_citations and "tool_calls" in response_data["choices"][0]["message"]:
                web_citations = self._extract_web_citations(response_data)
                if web_citations:
                    result["citations"] = web_citations
                    
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}"
            }
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing API response: {str(e)}")
            return {
                "success": False,
                "error": f"Error parsing API response: {str(e)}"
            }
            
    def _extract_web_citations(self, response_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract web citations from the VeniceAI response.
        
        Args:
            response_data: The full API response data
            
        Returns:
            List of citations with source information
        """
        citations = []
        
        try:
            # Navigate to web search tool calls
            tool_calls = response_data["choices"][0]["message"].get("tool_calls", [])
            for tool_call in tool_calls:
                if tool_call.get("type") == "function" and tool_call["function"].get("name") == "web_search":
                    function_args = json.loads(tool_call["function"].get("arguments", "{}"))
                    search_results = function_args.get("web_search_results", [])
                    
                    for result in search_results:
                        citation = {
                            "url": result.get("url", ""),
                            "title": result.get("title", ""),
                            "snippet": result.get("snippet", "")
                        }
                        citations.append(citation)
            
            # Fallback: if citations are in a different format, try the tool_responses field
            if not citations and "tool_responses" in response_data:
                tool_responses = response_data.get("tool_responses", [])
                for response in tool_responses:
                    if isinstance(response, dict) and "web_results" in response:
                        for result in response["web_results"]:
                            citation = {
                                "url": result.get("url", ""),
                                "title": result.get("title", ""),
                                "snippet": result.get("snippet", "")
                            }
                            citations.append(citation)
        except Exception as e:
            logger.error(f"Error extracting citations: {str(e)}")
        
        return citations
                
    def search_with_specific_sites(self, query: str, sites: List[str], **kwargs) -> Dict[str, Any]:
        """
        Perform a web search limited to specific websites.
        
        Args:
            query: The search query
            sites: List of websites to search (e.g., ["wikipedia.org", "cnn.com"])
            **kwargs: Additional parameters to pass to the search method
            
        Returns:
            Dict containing search results with citations if enabled
        """
        # Build a query that restricts results to specified sites
        site_restrictions = " OR ".join([f"site:{site}" for site in sites])
        enhanced_query = f"{query} ({site_restrictions})"
        
        return self.search(enhanced_query, **kwargs)
        
    def ask_with_context(self, 
                         query: str, 
                         context: str,
                         enable_web_search: bool = True,
                         **kwargs) -> Dict[str, Any]:
        """
        Ask a question with additional context, optionally using web search.
        
        Args:
            query: The question to ask
            context: Additional context to provide
            enable_web_search: Whether to enable web search or rely on context only
            **kwargs: Additional parameters to pass to the search method
            
        Returns:
            Dict containing response
        """
        if not self.api_key:
            return {"error": "VENICEAI_API_KEY not configured", "success": False}
            
        # Build payload with context
        payload = {
            "frequency_penalty": 0,
            "n": 1,
            "presence_penalty": 0,
            "temperature": kwargs.get("temperature", 0.3),
            "top_p": 1,
            "venice_parameters": {
                "include_venice_system_prompt": False,
                "enable_web_citations": kwargs.get("enable_citations", True),
                "enable_web_search": "on" if enable_web_search else "off",
                "max_search_results": kwargs.get("max_results", 3)
            },
            "parallel_tool_calls": False,
            "messages": [
                {
                    "content": kwargs.get("system_prompt", "You are a helpful assistant."),
                    "role": "system"
                },
                {
                    "content": f"Context information: {context}\n\nQuestion: {query}",
                    "role": "user"
                }
            ],
            "model": self.default_model
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept-Encoding": "",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Sending request with context and query: {query}")
            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            response_data = response.json()
            
            return {
                "success": True,
                "query": query,
                "response": response_data["choices"][0]["message"]["content"],
                "model": response_data.get("model", self.default_model),
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}"
            }