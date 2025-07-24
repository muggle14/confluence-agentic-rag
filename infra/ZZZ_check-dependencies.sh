#!/bin/bash

# Check dependencies for the deployment scripts
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}🔍 Checking Dependencies${NC}"
echo -e "${BLUE}==================================================${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required tools
echo -e "\n${YELLOW}Checking required tools...${NC}"

# Check Azure CLI
if command_exists az; then
    echo -e "${GREEN}✓ Azure CLI is installed${NC}"
    az_version=$(az --version | head -n 1)
    echo -e "  Version: $az_version"
else
    echo -e "${RED}✗ Azure CLI is not installed${NC}"
    echo -e "  Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check curl
if command_exists curl; then
    echo -e "${GREEN}✓ curl is installed${NC}"
else
    echo -e "${RED}✗ curl is not installed${NC}"
    exit 1
fi

# Check jq
if command_exists jq; then
    echo -e "${GREEN}✓ jq is installed${NC}"
else
    echo -e "${YELLOW}⚠️ jq is not installed (optional but recommended)${NC}"
    echo -e "  Install with: brew install jq (macOS) or apt-get install jq (Linux)"
fi

# Check Azure CLI login status
echo -e "\n${YELLOW}Checking Azure CLI login status...${NC}"
if az account show >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Azure CLI is logged in${NC}"
    subscription=$(az account show --query name -o tsv)
    echo -e "  Current subscription: $subscription"
else
    echo -e "${RED}✗ Not logged in to Azure${NC}"
    echo -e "  Run: az login"
    exit 1
fi

# Check environment variables
echo -e "\n${YELLOW}Checking environment variables...${NC}"

if [ -n "$AOAI_ENDPOINT" ]; then
    echo -e "${GREEN}✓ AOAI_ENDPOINT is set${NC}"
else
    echo -e "${YELLOW}⚠️ AOAI_ENDPOINT is not set${NC}"
    echo -e "  Set with: export AOAI_ENDPOINT='https://your-aoai.openai.azure.com/'"
fi

if [ -n "$AOAI_KEY" ]; then
    echo -e "${GREEN}✓ AOAI_KEY is set${NC}"
else
    echo -e "${YELLOW}⚠️ AOAI_KEY is not set${NC}"
    echo -e "  Set with: export AOAI_KEY='your-api-key'"
fi

echo -e "\n${BLUE}==================================================${NC}"
echo -e "${GREEN}Dependency check complete!${NC}"
echo -e "${BLUE}==================================================${NC}"