#!/bin/bash
# Start Move37 in development mode

# Terminal colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Move37 development environment${NC}"

# Set development ports
export API_PORT=8001
export FRONTEND_PORT=3000
export MCP_PORT=7777

# Activate virtual environment if it exists
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Check if frontend directory exists
if [ ! -d "frontend" ]; then
  echo -e "${YELLOW}Warning: 'frontend' directory not found${NC}"
  exit 1
fi

# Start the MCP server with debug flag and SSE transport
echo -e "${GREEN}Starting MCP server on port $MCP_PORT with SSE transport${NC}"
# Run with PYTHONPATH set to ensure proper module imports
PYTHONPATH=. python run_mcp_server.py --port $MCP_PORT --debug --transport sse &
MCP_PID=$!

# Wait for MCP server to start and check if it's running
echo -e "${BLUE}Waiting for MCP server to initialize...${NC}"
sleep 5
if ! ps -p $MCP_PID > /dev/null; then
  echo -e "${RED}MCP server failed to start. Check logs for errors.${NC}"
  exit 1
fi
echo -e "${GREEN}MCP server process started successfully.${NC}"

# Verify MCP server is responding to HTTP requests
echo -e "${BLUE}Verifying MCP server connectivity (will timeout after 10 seconds)...${NC}"

# Simple check with timeout - don't get stuck here
timeout 10 curl -s http://localhost:$MCP_PORT/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
  echo -e "${GREEN}MCP server is responding to HTTP requests.${NC}"
else
  echo -e "${YELLOW}Note: Could not verify MCP server HTTP connectivity.${NC}"
  echo -e "${YELLOW}This is normal if it's only using SSE for streams.${NC}"
  echo -e "${GREEN}Continuing with startup...${NC}"
fi

# Start the backend
echo -e "${GREEN}Starting backend on port $API_PORT${NC}"
PYTHONPATH=. python main.py &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${BLUE}Waiting for backend to initialize...${NC}"
sleep 5
if ! ps -p $BACKEND_PID > /dev/null; then
  echo -e "${RED}Backend failed to start. Check logs for errors.${NC}"
  exit 1
fi
echo -e "${GREEN}Backend started successfully.${NC}"

# Start the frontend with environment variables
echo -e "${GREEN}Starting frontend on port $FRONTEND_PORT${NC}"
cd frontend
# Create .env file with environment variables
echo "VITE_API_PORT=$API_PORT" > .env.development.local
npm run dev -- --port $FRONTEND_PORT &
FRONTEND_PID=$!

cd ..

echo -e "\n${BLUE}Development servers running:${NC}"
echo -e "MCP Server: http://localhost:$MCP_PORT"
echo -e "Backend: http://localhost:$API_PORT"
echo -e "Frontend: http://localhost:$FRONTEND_PORT"
echo -e "\n${BLUE}Press Ctrl+C to stop all services${NC}"

# Wait for Ctrl+C
trap "kill $MCP_PID $BACKEND_PID $FRONTEND_PID; echo -e '\n${GREEN}Development servers stopped${NC}'; exit" INT
wait 