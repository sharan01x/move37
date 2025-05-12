#!/bin/bash
# Start Move37 production environment

# Terminal colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Move37 Production Environment${NC}"

# Set production port (default is 8000)
export API_PORT=8000
export API_HOST="0.0.0.0"  # Make accessible on LAN
export MCP_PORT=7777

# Activate virtual environment if it exists
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Check if requirements are installed
if [ -f "requirements.txt" ]; then
  echo -e "${BLUE}Checking for dependencies...${NC}"
  pip install -r requirements.txt --quiet || echo -e "${YELLOW}Some dependencies could not be installed, continuing anyway...${NC}"
fi

# Install MCP dependencies if not already installed
echo -e "${BLUE}Checking/installing MCP dependencies...${NC}"
# Don't fail if dependencies can't be installed
pip install mcp fastmcp --quiet || echo -e "${YELLOW}MCP dependencies could not be installed, continuing anyway...${NC}"

# Check if frontend directory exists
if [ ! -d "frontend" ]; then
  echo -e "${YELLOW}Warning: 'frontend' directory not found${NC}"
else
  # Force rebuilding of frontend to apply any changes
  echo -e "${BLUE}Building frontend...${NC}"
  cd frontend
  npm install
  cd ..
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

# Start the MCP server - UPDATED to use the correct path
echo -e "${GREEN}Starting MCP server on port $MCP_PORT${NC}"
# Use PYTHONPATH to ensure modules are found correctly
PYTHONPATH=. python app/mcp/server.py --port $MCP_PORT --host "0.0.0.0" --transport sse &
MCP_PID=$!

# Wait for MCP server to start
sleep 5
if ! ps -p $MCP_PID > /dev/null; then
  echo -e "${RED}MCP server failed to start. Check logs for errors.${NC}"
  exit 1
fi
echo -e "${GREEN}MCP server process started successfully.${NC}"

# Start the backend server
echo -e "${GREEN}Starting backend server on $API_HOST:$API_PORT${NC}"

# Run in production mode with PYTHONPATH set
PYTHONPATH=. python main.py &
BACKEND_PID=$!

# Check if backend started successfully
echo -e "${BLUE}Waiting for backend to initialize...${NC}"
sleep 5
if ! ps -p $BACKEND_PID > /dev/null; then
  echo -e "${RED}Backend server failed to start. Check logs for errors.${NC}"
  exit 1
fi
echo -e "${GREEN}Backend server started successfully.${NC}"

# Start the frontend development server (accessible on LAN)
if [ -d "frontend" ]; then
  echo -e "${GREEN}Starting frontend server accessible on LAN${NC}"
  cd frontend
  npm run dev -- --host &
  FRONTEND_PID=$!
  cd ..

  # Check if frontend started successfully
  sleep 5
  if ! ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${YELLOW}Warning: Frontend server may have failed to start${NC}"
  else
    echo -e "${GREEN}Frontend server running (accessible on your local network)${NC}"
  fi
fi

# Show local IP addresses for easy access
echo -e "\n${BLUE}Your local IP addresses:${NC}"
if command -v ifconfig &> /dev/null; then
  ifconfig | grep "inet " | grep -v 127.0.0.1
elif command -v ip &> /dev/null; then
  ip addr | grep "inet " | grep -v 127.0.0.1
fi

echo -e "\n${BLUE}Access the application on another device using:${NC}"
echo -e "http://<YOUR-IP-ADDRESS>:$API_PORT (backend)"
if [ -n "$FRONTEND_PID" ]; then
  echo -e "http://<YOUR-IP-ADDRESS>:5173 (frontend)"
fi

echo -e "\n${BLUE}Note: Your frontend is now configured to connect to the backend at port 8000${NC}"
echo -e "\n${BLUE}Press Ctrl+C to stop all services${NC}"

# Wait for all background processes
wait 