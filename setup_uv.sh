#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Move37 setup with uv...${NC}"

# Check if Python 3.11 is installed
if ! command -v python3.11 &> /dev/null; then
    echo -e "${RED}Python 3.11 is not installed. Please install it first.${NC}"
    echo "Visit https://www.python.org/downloads/ to download Python 3.11"
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}uv is not installed. Please install uv first.${NC}"
    echo "Visit https://github.com/astral-sh/uv for installation instructions"
    exit 1
fi

# Create virtual environment using uv in .venv directory
echo -e "${YELLOW}Creating virtual environment with uv in ./.venv...${NC}"
uv venv .venv --python=python3.11

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Install requirements using uv
echo -e "${YELLOW}Installing dependencies with uv...${NC}"
if [ -f requirements.txt ]; then
    uv pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Dependencies installed successfully!${NC}"
    else
        echo -e "${RED}Error installing dependencies. Some packages may need to be installed individually.${NC}"
        
        # Try installing packages that might cause trouble individually
        echo -e "${YELLOW}Attempting to install faiss-cpu separately...${NC}"
        uv pip install faiss-cpu --no-build-isolation # faiss-cpu can sometimes need this
        # Add other problematic packages here if needed
    fi
else
    echo -e "${RED}requirements.txt not found. Skipping dependency installation.${NC}"
fi

# Download spacy model
echo -e "${YELLOW}Downloading Spacy model (en_core_web_sm)...${NC}"
python -m spacy download en_core_web_sm

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Spacy model downloaded successfully!${NC}"
else
    echo -e "${RED}Error downloading Spacy model. Please try manually: python -m spacy download en_core_web_sm${NC}"
fi

echo -e "${GREEN}Move37 setup with uv completed!${NC}"
echo -e "${YELLOW}To activate the environment in the future, run: source .venv/bin/activate${NC}"