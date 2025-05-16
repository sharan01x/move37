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

# Ensure pip, setuptools, and wheel are installed in the venv by uv
echo -e "${YELLOW}Ensuring pip, setuptools, and wheel are installed by uv...${NC}"
uv pip install pip setuptools wheel
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install pip/setuptools/wheel with uv. Please check uv installation and network. Exiting.${NC}"
    exit 1
fi

# Install requirements using uv
echo -e "${YELLOW}Installing dependencies with uv...${NC}"
if [ -f requirements.txt ]; then
    # First try installing all requirements at once
    uv pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}Attempting to install packages individually...${NC}"
        
        # Read requirements.txt and install each package individually
        while IFS= read -r package || [ -n "$package" ]; do
            # Skip empty lines and comments
            [[ -z "$package" || "$package" =~ ^[[:space:]]*# ]] && continue
            
            # Remove version specifiers for individual installation
            package_name=$(echo "$package" | sed -E 's/([^=<>!~]+).*/\1/')
            
            echo -e "${YELLOW}Installing $package_name...${NC}"
            
            # Special handling for faiss-cpu
            if [[ "$package_name" == "faiss-cpu" ]]; then
                uv pip install "$package" --no-build-isolation
            else
                uv pip install "$package"
            fi
            
            if [ $? -ne 0 ]; then
                echo -e "${RED}Failed to install $package_name. Continuing with other packages...${NC}"
            fi
        done < requirements.txt
    fi
else
    echo -e "${RED}requirements.txt not found. Skipping dependency installation.${NC}"
fi

# Download spacy model using uv pip install from URL
echo -e "${YELLOW}Downloading Spacy model (en_core_web_sm v3.7.1) using uv pip install from URL...${NC}"
uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1.tar.gz#egg=en_core_web_sm

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Spacy model downloaded successfully!${NC}"
else
    echo -e "${RED}Error downloading Spacy model. Please try manually: uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1.tar.gz#egg=en_core_web_sm${NC}"
fi

# Install Playwright browser binaries (needed for browser_use library)
echo -e "${YELLOW}Installing Playwright browser binaries...${NC}"
python -m playwright install
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Playwright browser binaries installed successfully!${NC}"
else
    echo -e "${RED}Error installing Playwright browser binaries. Please try manually: python -m playwright install${NC}"
fi

echo -e "${GREEN}Move37 setup with uv completed!${NC}"
echo -e "${YELLOW}To activate the environment in the future, run: source .venv/bin/activate${NC}"