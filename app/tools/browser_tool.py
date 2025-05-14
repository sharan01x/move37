import asyncio
import logging
from langchain_ollama import ChatOllama
from browser_use import Agent, Browser, BrowserConfig

# Get the model name from config.py
from app.core.config import BROWSER_LLM_MODEL, BROWSER_BINARY_PATH

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize the model
llm = ChatOllama(model=BROWSER_LLM_MODEL, num_ctx=32000)

async def run_browser_task(task: str, user_id: str = None) -> str:
    """
    Runs a browser-based task using the browser_use agent.

    Args:
        task: The description of the task to perform.
        user_id: (optional) The user ID for memory config (if needed in future).

    Returns:
        A string containing the result of the task or an error message.
    """
    logger.info(f"Received browser task: {task}")
    browser = Browser(
        config=BrowserConfig(
            browser_binary_path=BROWSER_BINARY_PATH, 
            headless=True
        )
    )
    try:
        agent = Agent(
            task=task,
            browser=browser,  # Use the configured browser
            llm=llm,          # Uses the global llm instance
        )
        result = await agent.run()
        logger.info(f"Browser task '{task}' completed successfully.")
        return str(result)
    except Exception as e:
        logger.error(f"Error during browser task '{task}': {e}", exc_info=True)
        return f"Failed to execute browser task: '{task}'. Error: {e}"
    finally:
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

