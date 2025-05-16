#!/bin/bash
# Start Move37 production environment

# Terminal colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Set KMP_DUPLICATE_LIB_OK for Mac systems
if [[ "$OSTYPE" == "darwin"* ]]; then
    export KMP_DUPLICATE_LIB_OK=TRUE
fi

echo -e "${BLUE}Starting Move37 Production Environment${NC}"

# Set production port (default is 8000)
export API_PORT=8000
export API_HOST="localhost"  # Keep backend local-only
export MCP_PORT=7777
export FRONTEND_PORT=3737  # Set frontend port to 3737

# Pass API_PORT to frontend
export VITE_API_PORT=$API_PORT

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Function to handle cleanup
cleanup() {
    echo -e "\n${BLUE}Shutting down services...${NC}"
    
    # Kill processes in reverse order of startup
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$MCP_PID" ]; then
        kill $MCP_PID 2>/dev/null || true
    fi
    
    # Wait for processes to finish
    wait 2>/dev/null || true
    
    echo -e "${GREEN}All services stopped${NC}"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM EXIT

# Start the MCP server
PYTHONPATH=. python app/mcp/server.py --port $MCP_PORT --host localhost --transport sse > /dev/null 2>&1 &
MCP_PID=$!

# Wait for MCP server to start
sleep 5
if ! ps -p $MCP_PID > /dev/null; then
  echo -e "${RED}MCP server failed to start. Check logs for errors.${NC}"
  exit 1
fi

# Start the backend server
PYTHONPATH=. python main.py > /dev/null 2>&1 &
BACKEND_PID=$!

# Check if backend started successfully
sleep 5
if ! ps -p $BACKEND_PID > /dev/null; then
  echo -e "${RED}Backend server failed to start. Check logs for errors.${NC}"
  exit 1
fi

# Start the frontend development server
if [ -d "frontend" ]; then
  cd frontend
  npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT > /dev/null 2>&1 &
  FRONTEND_PID=$!
  cd ..
fi

# Get network interfaces and display access information
echo -e "\n${GREEN}Access Move37 in the following ways:${NC}"
echo -e "Local: http://localhost:$FRONTEND_PORT"

# Get network interfaces
if command -v ifconfig &> /dev/null; then
  ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print "Network: http://" $2 ":'$FRONTEND_PORT'"}'
elif command -v ip &> /dev/null; then
  ip addr | grep "inet " | grep -v 127.0.0.1 | awk '{print "Network: http://" $2 ":'$FRONTEND_PORT'"}'
fi

echo -e "\n${BLUE}Press Ctrl+C to stop all services${NC}"

# Wait for all background processes
wait 