import asyncio
import logging
import os
import sys
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()
# Load environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    print("Using OpenAI")
else:
    print("Using Ollama")

from pathlib import Path

# Add the project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig

# Now the import will work both when imported as a module and when run directly
from app.core.config import ( 
    BROWSER_BINARY_PATH,
    BROWSER_PROFILE_PATH,
    OPENAI_API_KEY,
    OPENAI_API_URL,
    OLLAMA_BROWSER_EXECUTION_MODEL,
    OLLAMA_BROWSER_PLANNING_MODEL,
    OPENAI_BROWSER_EXECUTION_MODEL,
    OPENAI_BROWSER_PLANNING_MODEL
)

# Initialize logger first so we can use it for the API connection check
logger = logging.getLogger(__name__)

# We need to get the VeniceAI LLM setup here
if OPENAI_API_KEY:
    # Create the LLM with appropriate configuration
    execution_llm = ChatOpenAI(
        model_name=OPENAI_BROWSER_EXECUTION_MODEL,
        temperature=0.3,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_URL
    )

    planning_llm = ChatOpenAI(
        model_name=OPENAI_BROWSER_PLANNING_MODEL,
        temperature=0.3,
        openai_api_key=OPENAI_API_KEY,
        openai_api_base=OPENAI_API_URL
    )

else:
    # Fallback to Ollama if the other services are not available
    execution_llm = ChatOllama(model=OLLAMA_BROWSER_EXECUTION_MODEL, num_ctx=32000)
    planning_llm = ChatOllama(model=OLLAMA_BROWSER_PLANNING_MODEL)



async def run_browser_task(task: str, user_id: str = None) -> str:
    """
    Runs a browser-based task using the browser_use agent.
    Creates a fresh browser context for each task and uses a separate
    planning model for improved performance.

    Args:
        task: The description of the task to perform.
        user_id: (optional) The user ID for memory config (if needed in future).

    Returns:
        A string containing the result of the task or an error message.
    """
    # Handle case where task might be passed as a JSON object or JSON string
    if isinstance(task, str):
        # Handle the specific error case we're seeing
        if task == "{'title': 'Task', 'type': 'string'}" or task.startswith('{') and task.endswith('}'):
            try:
                import json
                # Replace single quotes with double quotes for proper JSON parsing
                fixed_task = task.replace("'", '"')
                task_obj = json.loads(fixed_task)
                
                if isinstance(task_obj, dict):
                    if 'title' in task_obj and task_obj['title'] == 'Task':
                        logger.warning(f"Received placeholder task: {task}. Getting task from user_id.")
                        
                        # Abort and return a message to the user
                        return "There was an error with the task. Please provide a valid task description."

            except Exception as e:
                logger.warning(f"Failed to parse JSON task: {e}. Using task string as is.")
    
    logger.info(f"Executing browser task: {task}")
    
    # Create a browser instance with the configured profile path
    # This ensures user settings and preferences are preserved where needed
    browser = Browser(
        config=BrowserConfig(
            browser_binary_path=BROWSER_BINARY_PATH,
            browser_profile_path=BROWSER_PROFILE_PATH
        )
    )
    try:
        agent = Agent(
            task=task,
            browser=browser,
            llm=execution_llm,
            planner_llm=planning_llm,
            planner_interval=3,
            extend_system_message="Close the browser tab when done with your task. Use https://duckduckgo.com or https://search.brave.com/ for web searches unless the user asks for a specific search engine to be used."
        )
        result = await agent.run()
        logger.info(f"Browser task '{task}' completed successfully.")
        return str(result)
    except Exception as e:
        logger.error(f"Error during browser task '{task}': {e}", exc_info=True)
        return f"Failed to execute browser task: '{task}'. Error: {e}"
    finally:
        # Just close the browser when done
        await browser.close()

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run a browser task with browser_use.")
    parser.add_argument("--task", type=str, required=False, help="The task to perform in the browser.")
    parser.add_argument("--user_id", type=str, default="default_user", help="User ID for memory config.")
    args = parser.parse_args()

    task = args.task or "Get the price of Ethereum in USD"
    print(f"Running task: {task}")

    result = await run_browser_task(task, user_id=args.user_id)
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    # Setup basic logging for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main())

