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

# Activate virtual environment if it exists
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Check if requirements are installed
if [ -f "requirements.txt" ]; then
  echo -e "${BLUE}Checking for dependencies...${NC}"
  pip install -r requirements.txt --quiet
fi

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

# Start the backend server
echo -e "${GREEN}Starting backend server on $API_HOST:$API_PORT${NC}"

# Run in production mode 
python main.py &
BACKEND_PID=$!

# Check if backend started successfully
sleep 2
if ! ps -p $BACKEND_PID > /dev/null; then
  echo -e "${RED}Backend server failed to start${NC}"
  exit 1
fi

# Start the frontend development server (accessible on LAN)
if [ -d "frontend" ]; then
  echo -e "${GREEN}Starting frontend server accessible on LAN${NC}"
  cd frontend
  npm run dev -- --host &
  FRONTEND_PID=$!
  cd ..

  # Check if frontend started successfully
  sleep 2
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

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; echo -e '\n${GREEN}Servers stopped${NC}'; exit" INT
wait 