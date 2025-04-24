#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Butterfly agent for the LifeScribe application.
Specializes in posting messages to social media platforms via GUI automation.
"""

from typing import Dict, Any, Optional, Union, Callable, List, Tuple
from crewai import Task
import asyncio
import json
import os
import re
import requests
import traceback

from app.agents.base_agent import BaseAgent
from app.core.config import BUTTERFLY_LLM_PROVIDER, BUTTERFLY_LLM_MODEL, CHAT_API_URL # Assuming these exist
from app.tools.social_media_tools import available_tools, get_user_accounts # Import the list of tools and the utility function

class ButterflyAgent(BaseAgent):
    """
    Agent specialized in posting text content to social media platforms.
    """

    def __init__(self):
        """Initialize the Butterfly agent."""
        super().__init__(
            name="Butterfly",
            description="I specialize in posting messages to social media accounts like Twitter, LinkedIn, etc.",
            role="Social Media Poster",
            goal="Post user-provided text content to the specified social media platform and account using available tools.",
            tools=available_tools, # Pass the imported list of tools
            llm_provider=BUTTERFLY_LLM_PROVIDER, # Use specific or default LLM settings
            llm_model=BUTTERFLY_LLM_MODEL
        )
        # Create a mapping of channel IDs to tools for easier lookup
        self.channel_tool_map = {}
        self._initialize_channel_tool_map()

    def _initialize_channel_tool_map(self):
        """
        Initialize the mapping between channel IDs and their corresponding tools.
        This makes it easier to find the right tool for a given channel.
        """
        for tool in self.agent.tools:
            if tool.name.startswith("Post to "):
                # Extract channel name from tool name (e.g., "Post to Twitter" -> "twitter")
                channel = tool.name.replace("Post to ", "").lower()
                self.channel_tool_map[channel] = tool
        
        print(f"[ButterflyAgent] Initialized channel-tool map: {self.channel_tool_map.keys()}")

    def get_user_accounts(self, user_id: str) -> Union[Dict[str, Any], str]:
        """
        Loads and returns the social media channel configurations for a given user.

        Args:
            user_id: The ID of the user.

        Returns:
            A dictionary containing the user's channel configurations,
            or an error message string if the config file is not found or invalid.
        """
        # Use the utility function from social_media_tools to get all accounts
        accounts_dict = get_user_accounts(user_id)
        
        if not accounts_dict:
            return f"No social media accounts found for user {user_id}."
            
        try:
            # Format accounts data for display in the prompt
            # Build a structured representation categorized by channel_id  
            channels = {}
            for account_name, account in accounts_dict.items():
                channel_id = account.get("channel_id")
                if channel_id:
                    if channel_id not in channels:
                        channels[channel_id] = []
                    channels[channel_id].append({
                        "name": account_name,
                        "type": account.get("type", "unspecified"),
                        "description": account.get("description", "")
                    })
            
            if not channels:
                print(f"[ButterflyAgent] No channel configurations found in accounts for user {user_id}")
                return f"No channel configurations found for user {user_id}."
                
            # Format as JSON for clear presentation in the prompt
            return json.dumps(channels, indent=2)
            
        except Exception as e:
            print(f"[ButterflyAgent] Error processing account data for user {user_id}: {e}")
            return f"Error processing account data for user {user_id}: {str(e)}"

    async def _post_to_accounts(self, content: str, targets: List[Dict[str, str]], user_id: str, attachment_file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Posts the same content to one or more accounts across different channels.
        
        Args:
            content: The content to post
            targets: List of dicts with channel_id and account_name keys
            user_id: The user ID for context
            attachment_file_path: Optional path to an attached image or video file.
            
        Returns:
            Dictionary with results for each posting attempt
        """
        results = []
        overall_success = True
        
        for target in targets:
            channel_id = target.get("channel_id")
            account_name = target.get("account_name")
            
            if not channel_id or not account_name:
                results.append({
                    "channel": channel_id or "unknown",
                    "account": account_name or "unknown",
                    "success": False,
                    "message": "Missing channel or account information"
                })
                overall_success = False
                continue
                
            # Get the appropriate tool for this channel
            tool = self.channel_tool_map.get(channel_id.lower())
            if not tool:
                results.append({
                    "channel": channel_id,
                    "account": account_name,
                    "success": False,
                    "message": f"No posting tool available for channel '{channel_id}'"
                })
                overall_success = False
                continue
                
            try:
                print(f"[ButterflyAgent] Posting to {channel_id}/{account_name}: {content[:30]}...")
                if attachment_file_path:
                    print(f"[ButterflyAgent] With attachment: {attachment_file_path}")
                
                # Set user_id context on the tool
                tool.user_id = user_id
                
                try:
                    # Pass image_path (None if not present)
                    result = tool._run(account_name=account_name, content=content, image_path=attachment_file_path)
                    
                    success = "successfully" in result.lower() and "error" not in result.lower()
                    results.append({
                        "channel": channel_id,
                        "account": account_name,
                        "success": success,
                        "message": result
                    })
                    
                    if not success:
                        overall_success = False
                finally:
                    # Always reset the user_id to avoid leaking context
                    tool.user_id = None
                    
            except Exception as e:
                print(f"[ButterflyAgent] Error posting to {channel_id}/{account_name}: {e}")
                results.append({
                    "channel": channel_id,
                    "account": account_name,
                    "success": False,
                    "message": f"Error posting to {channel_id}/{account_name}: {str(e)}"
                })
                overall_success = False
                
        # Format results for display
        result_summary = "The following were the results of the task:\n"
        for result in results:
            status = "✅ Success" if result["success"] else "❌ Failed"
            result_summary += f"* {result['channel']}/{result['account']}: {status}\n"
            if not result["success"]:
                result_summary += f"  - {result['message']}\n"
                
        return {
            "agent_name": self.name,
            "overall_success": overall_success,
            "results": results,
            "answer": result_summary,
            "json_data": {
                "content": content,
                "posting_results": [
                    {
                        "channel": r["channel"],
                        "account": r["account"],
                        "success": r["success"],
                        "message": r["message"]
                    } for r in results
                ],
                "overall_success": overall_success
            }
        }
        
    async def answer_query_async(self, query: str, user_id: str, message_callback: Optional[Callable] = None, attachment_file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes a user query requesting a social media post.

        Args:
            query: The user's request (e.g., "Post 'Hello World' to my personal Twitter account").
            user_id: The ID of the user (used for account settings).
            message_callback: Callback function for sending status messages.
            attachment_file_path: Optional path to an attached image or video file.

        Returns:
            A dictionary formatted response indicating the success or failure of the posting attempt.
        """
        try:
            self.set_message_callback(message_callback)
            await self.send_message("Butterfly is analyzing your social media post request...")

            # Use LLM to extract key information from the request
            user_prompt = f"""
            USER'S REQUEST: 
            
            {query}
                
            -------------

            INSTRUCTIONS:
            1. Analyze the user's request to determine these specific parameters:
               - content: The exact content to be posted (the message itself). This content may be enclosed within quotes or appear after a colon. 
               - channel: The social media platform to post to (e.g., "Twitter", "BlueSky", "Lens", "Mastodon", "LinkedIn", "X", "Farcaster" etc.), if mentioned. The channel may be mentioned in lowecase, may be enclosed within quotes or be led by a '@' symbol. Remove the '@' if present when responding with the channel name.
               - account_type: The type of account to post to (e.g., "personal", "company", "professional", "work", "anonymous", "third-party", "bot", etc.), if mentioned
               - account_name: A specific account name to post to, if mentioned. It may include the '@' symbol before the account name. Remove the leading '@' if present when responding with the account name. The account name may alternatively be enclosed within quotes.
            
            2. For each parameter:
               - If it's explicitly mentioned or can be clearly inferred, include it
               - If it's not mentioned or unclear, set it to null
               - The content parameter is required and must not be null
            
            3. Return your analysis in the following JSON format:
               {{
                 "content": "the exact content to post",
                 "channel": "platform_name or null",
                 "account_type": "account_type or null",
                 "account_name": "specific_account_name or null"
               }}
            
            4. Do not attempt to determine which specific accounts to post to beyond these parameters.
               The system will handle that based on the parameters you extract.

            Examples:
               1. Post "Hello there!" to my personal Twitter account  --- This means that the user wants to post "Hello there!" to the accounts where the channel is "Twitter" and the account type is "personal". Your response should therefore be:
               {{
                 "content": "Hello there!",
                 "channel": "Twitter",
                 "account_type": "personal",
                 "account_name": null
               }}   

               2. Post "This is a longer post to be used as content" to my anonymous accounts --- This means that the user wants to post "This is a longer post to be used as content" to the accounts where the channel could be anything, but the account type is "anonymous". Your response should therefore be:
               
               {{
                 "content": "This is a longer post to be used as content",
                 "channel": null,
                 "account_type": "anonymous",
                 "account_name": null
               }}

            Now process the user's request.
            """

            # Execute the prompt above against an LLM and output the result as is for now
            # Using Ollama API with the Conductor's LLM configuration
            try:
                 # Using the shared queryLLM method from BaseAgent instead of direct API calls
                response_text = await self.queryLLM(
                    user_prompt=user_prompt,
                    model=BUTTERFLY_LLM_MODEL,
                    system_prompt=None,
                    stream=False,
                    temperature=0.0
                )

                print(f"[Butterfly Agent] The LLM Output: \n {response_text}")

                # Extract JSON from response text
                json_str = None
                json_blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)```', response_text)
                if json_blocks:
                    json_str = json_blocks[0].strip()
                else:
                    # Try to extract JSON directly
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response_text[json_start:json_end]

                # Parse the JSON
                if json_str:
                    task_parameters = json.loads(json_str)
                    
                    # Now use parameters to filter accounts
                    content = task_parameters.get("content")
                    channel = task_parameters.get("channel")
                    account_type = task_parameters.get("account_type")
                    account_name = task_parameters.get("account_name")
                    # Normalize account_name by stripping leading '@' if present
                    if account_name and account_name.startswith("@"): 
                        account_name = account_name[1:]
                    
                    # Get filtered accounts
                    accounts_list = get_user_accounts(user_id, account_type=account_type, channel=channel)
                    print(f"[Butterfly Agent] List of accounts to post the text to:\n {accounts_list}")
                    
                    # Now, if the accounts_list is not empty, send the list of accounts to the _post_to_accounts function to execute
                    if accounts_list:
                        # Ensure we have content to post
                        if not content:
                            return self.format_response("Could not extract content to post from your request. Please specify the message more clearly.")
                        
                        # If a specific account name was mentioned and found, use only that account
                        if account_name and account_name in accounts_list:
                            targets = [{
                                "channel_id": accounts_list[account_name]["channel_id"],
                                "account_name": account_name
                            }]
                        else:
                            # Otherwise use all filtered accounts
                            targets = [
                                {
                                    "channel_id": account["channel_id"],
                                    "account_name": name
                                } 
                                for name, account in accounts_list.items()
                            ]
                        
                        # Notify the user about the posting operation
                        if attachment_file_path:
                            await self.send_message(f"[Butterfly Agent] Butterfly will post to {len(targets)} account(s) with attachment")
                        else:
                            await self.send_message(f"[Butterfly Agent] Butterfly will post to {len(targets)} account(s)")
                        
                        # Post the content to the targeted accounts
                        result = await self._post_to_accounts(content, targets, user_id, attachment_file_path)
                        
                        # Clean up temporary file if it exists
                        if attachment_file_path and os.path.exists(attachment_file_path):
                            try:
                                os.remove(attachment_file_path)
                                print(f"[Butterfly Agent] Deleted temporary file: {attachment_file_path}")
                            except Exception as e:
                                print(f"[Butterfly Agent] Failed to delete temporary file: {e}")
                        
                        return result
                    else:
                        # Construct appropriate error message based on what filters were applied
                        if channel and account_type:
                            error_msg = f"No {account_type} accounts found for {channel}."
                        elif channel:
                            error_msg = f"No accounts found for {channel}."
                        elif account_type:
                            error_msg = f"No {account_type} accounts found."
                        else:
                            error_msg = "No social media accounts found that match your criteria."
                        
                        return self.format_response(error_msg)
                else:
                    # Handle case where we couldn't extract valid JSON
                    print(f"[Butterfly Agent] Could not parse valid JSON from LLM response: {response_text}")
                    return self.format_response("Could not understand your request. Please try again with clearer instructions about what to post and where.")
                
                if not response_text:
                    raise ValueError("Empty response from Ollama")
                    
            except requests.RequestException as e:
                print(f"[Butterfly Agent] Ollama API request failed: {e}")
                raise
            except ValueError as e:
                print(f"[Butterfly Agent] Failed to parse Ollama response: {e}")
                raise

        except Exception as e:
            print(f"[Butterfly Agent] Error processing query: {e}")
            traceback.print_exc()
            return {
                "agent_name": self.name,
                "answer": "An error occurred while processing your request. Please try again later.",
                "json_data": {
                    "message": "An error occurred while processing your request. Please try again later.",
                    "success": False,
                    "error": True
                }
            }

    def format_response(self, result: str) -> Dict[str, Any]:
        """
        Formats the agent's final result string into a standard dictionary 
        with structured JSON data suitable for LLM consumption.
        """
        # If result is already a dictionary
        if isinstance(result, dict):
            # Ensure it has json_data field
            if "json_data" not in result:
                result["json_data"] = {
                    "message": result.get("answer", ""),
                    "success": result.get("overall_success", False),
                    "results": result.get("results", [])
                }
            return result
        
        # If result is a string message
        else:
            return {
                "agent_name": self.name,
                "answer": str(result).strip() if result else "No response generated.",
                "json_data": {
                    "message": str(result).strip() if result else "No response generated.",
                    "success": False,
                    "error": True if result and "error" in str(result).lower() else False
                }
            }