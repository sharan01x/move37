#!/bin/bash
# Start Move37 in development mode

# Terminal colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Set KMP_DUPLICATE_LIB_OK for Mac systems
if [[ "$OSTYPE" == "darwin"* ]]; then
    export KMP_DUPLICATE_LIB_OK=TRUE
fi

echo -e "${BLUE}Starting Move37 development environment${NC}"

# Set development ports
export API_PORT=8001
export FRONTEND_PORT=3737
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

# Function to handle cleanup
cleanup() {
    echo -e "\n${BLUE}Shutting down services...${NC}"
    
    # Kill processes in reverse order of startup
    if [ ! -z "$FRONTEND_PID" ]; then
        echo -e "${BLUE}Stopping frontend...${NC}"
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$BACKEND_PID" ]; then
        echo -e "${BLUE}Stopping backend...${NC}"
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$MCP_PID" ]; then
        echo -e "${BLUE}Stopping MCP server...${NC}"
        kill $MCP_PID 2>/dev/null || true
    fi
    
    # Wait for processes to finish
    wait 2>/dev/null || true
    
    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM EXIT

# Start the MCP server with debug flag and SSE transport
echo -e "${GREEN}Starting MCP server on port $MCP_PORT with SSE transport${NC}"
# Run with PYTHONPATH set to ensure proper module imports
PYTHONPATH=. python app/mcp/server.py --port $MCP_PORT --host localhost --transport sse &
MCP_PID=$!

# Wait for MCP server to start and check if it's running
echo -e "${BLUE}Waiting for MCP server to initialize...${NC}"
sleep 5
if ! ps -p $MCP_PID > /dev/null; then
  echo -e "${RED}MCP server failed to start. Check logs for errors.${NC}"
  exit 1
fi
echo -e "${GREEN}MCP server process started successfully.${NC}"

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
npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT &
FRONTEND_PID=$!

cd ..

# Show local IP addresses for easy access
echo -e "\n${BLUE}Your local IP addresses:${NC}"
if command -v ifconfig &> /dev/null; then
  ifconfig | grep "inet " | grep -v 127.0.0.1
elif command -v ip &> /dev/null; then
  ip addr | grep "inet " | grep -v 127.0.0.1
fi

echo -e "\n${BLUE}Development servers running:${NC}"
echo -e "MCP Server: http://localhost:$MCP_PORT (local only)"
echo -e "Backend: http://localhost:$API_PORT (local only)"
echo -e "Frontend: http://localhost:$FRONTEND_PORT (or use your local IP/network name)"
echo -e "\n${BLUE}You can access the frontend from other devices using your local IP or network name (e.g., slingshot.local)${NC}"
echo -e "\n${BLUE}Press Ctrl+C to stop all services${NC}"

# Wait for all background processes
wait 