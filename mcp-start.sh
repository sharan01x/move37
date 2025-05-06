#!/bin/bash

# Script to start the Move37 MCP server
echo "Starting Move37 MCP Server..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install MCP dependencies if not already installed
echo "Checking/installing MCP dependencies..."
pip install mcp fastmcp

# Make script executable if it's not
if [ ! -x "run_mcp_server.py" ]; then
    echo "Making server script executable..."
    chmod +x run_mcp_server.py
fi

# Start the server
echo "Launching MCP server..."
python run_mcp_server.py "$@" 