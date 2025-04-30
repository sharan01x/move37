#!/bin/bash
# Start Move37 in development mode

# Terminal colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Move37 development environment${NC}"

# Set development ports
export API_PORT=8001
export FRONTEND_PORT=3000

# Activate virtual environment if it exists
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Check if frontend directory exists
if [ ! -d "frontend" ]; then
  echo -e "${YELLOW}Warning: 'frontend' directory not found${NC}"
  exit 1
fi

# Start the backend
echo -e "${GREEN}Starting backend on port $API_PORT${NC}"
python main.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start the frontend with environment variables
echo -e "${GREEN}Starting frontend on port $FRONTEND_PORT${NC}"
cd frontend
# Create .env file with environment variables
echo "VITE_API_PORT=$API_PORT" > .env.development.local
npm run dev -- --port $FRONTEND_PORT &
FRONTEND_PID=$!

cd ..

echo -e "\n${BLUE}Development servers running:${NC}"
echo -e "Backend: http://localhost:$API_PORT"
echo -e "Frontend: http://localhost:$FRONTEND_PORT"
echo -e "\n${BLUE}Press Ctrl+C to stop all services${NC}"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; echo -e '\n${GREEN}Development servers stopped${NC}'; exit" INT
wait 