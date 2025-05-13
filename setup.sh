#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Move37 setup...${NC}"

# Check if Python 3.12 is installed
if ! command -v python3.12 &> /dev/null; then
    echo -e "${RED}Python 3.12 is not installed. Please install it first.${NC}"
    echo "Visit https://www.python.org/downloads/ to download Python 3.12"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}pip is not installed. Please install pip first.${NC}"
    exit 1
fi

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3.12 -m venv venv

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install requirements
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Check if installation was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Dependencies installed successfully!${NC}"
else
    echo -e "${RED}Error installing dependencies. Please check the error messages above.${NC}"
    exit 1
fi

# Download spacy model
echo -e "${YELLOW}Downloading spacy model...${NC}"
python -m spacy download en_core_web_sm

# Verify installation
echo -e "${YELLOW}Verifying installation...${NC}"
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('Spacy loaded successfully!')"
python -c "import fastmcp; print('Fastmcp loaded successfully!')"

echo -e "${GREEN}Setup completed successfully!${NC}"
echo -e "${YELLOW}To activate the virtual environment, run:${NC}"
echo "source venv/bin/activate" 