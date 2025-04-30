#!/bin/bash
# Start Move37 production environment

# Terminal colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Move37...{NC}"

# Set production port (default is 8000)
export API_PORT=8000

# Activate virtual environment if it exists
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Check if requirements are installed
if [ -f "requirements.txt" ]; then
  echo -e "${BLUE}Checking for dependencies...${NC}"
  pip install -r requirements.txt --quiet
fi

# Start the backend server
echo -e "${GREEN}Starting backend server on port $API_PORT${NC}"

# Run in production mode
python main.py &
BACKEND_PID=$!

# Check if backend started successfully
sleep 2
if ! ps -p $BACKEND_PID > /dev/null; then
  echo -e "${RED}Backend server failed to start${NC}"
  exit 1
fi

echo -e "${GREEN}Backend server running at http://localhost:$API_PORT${NC}"
echo -e "\n${BLUE}Press Ctrl+C to stop all services${NC}"

# Wait for Ctrl+C
trap "kill $BACKEND_PID; echo -e '\n${GREEN}Servers stopped${NC}'; exit" INT
wait 