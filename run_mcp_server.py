#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to start the Move37 MCP server.
"""

import argparse
import logging
import asyncio
from app.mcp.server import mcp  # Import the FastMCP instance

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_tools_async():
    """Get the tools from the MCP server asynchronously."""
    try:
        tools = await mcp.get_tools()
        return tools
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        return []

def get_tools_sync():
    """Get tools synchronously by running the async function in a new event loop."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tools = loop.run_until_complete(get_tools_async())
        loop.close()
        return tools
    except Exception as e:
        logger.error(f"Error in get_tools_sync: {e}")
        return []

def main():
    """Main entry point for starting the MCP server."""
    parser = argparse.ArgumentParser(description="Start the Move37 MCP server")
    parser.add_argument('--port', type=int, default=7777,
                        help='Port to run the server on (default: 7777)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output')
    parser.add_argument('--transport', choices=['stdio', 'sse'], default='sse',
                        help='Transport method to use (default: sse)')
    
    args = parser.parse_args()
    
    # Check if debug is enabled
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Verify tools are registered using the synchronous wrapper
    all_tools = get_tools_sync()
    
    logger.info(f"MCP server has {len(all_tools)} registered tools:")
    for tool in all_tools:
        logger.info(f"  - {tool}")
    
    if not all_tools:
        logger.warning("No tools registered with the MCP server. Check server implementation.")
    
    transport = args.transport
    logger.info(f"Starting Move37 MCP Server on port {args.port} with {transport} transport")
    print(f"Starting Move37 MCP server on port {args.port} with {transport} transport")
    
    # Use the specified transport
    if transport == 'sse':
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main() 