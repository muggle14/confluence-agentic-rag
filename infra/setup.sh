#!/bin/bash

# Confluence Q&A System - Complete Setup Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Confluence Q&A System - Complete Setup${NC}"
echo -e "${BLUE}========================================${NC}"

# Check prerequisites
echo -e "\n${YELLOW}📋 Checking Prerequisites${NC}"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI is not installed. Please install it first.${NC}"
    echo -e "${YELLOW}💡 Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli${NC}"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ jq is not installed. Please install it first.${NC}"
    echo -e "${YELLOW}💡 Install with: brew install jq (macOS) or apt-get install jq (Ubuntu)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Step 1: Setup environment file
echo -e "\n${YELLOW}📝 Step 1: Setting up environment file${NC}"
if [ ! -f "../.env" ]; then
    echo -e "${YELLOW}📋 Copying environment template${NC}"
    cp .env.template ../.env
    echo -e "${GREEN}✅ Environment file created at ../.env${NC}"
    echo -e "${YELLOW}⚠️  Please review and update the environment variables if needed${NC}"
else
    echo -e "${GREEN}✅ Environment file already exists${NC}"
fi

# Step 2: Azure Login
echo -e "\n${YELLOW}🔐 Step 2: Azure Authentication${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}🔑 Please login to Azure${NC}"
    az login
else
    echo -e "${GREEN}✅ Already logged in to Azure${NC}"
fi

# Show current subscription
current_sub=$(az account show --query id -o tsv)
echo -e "${BLUE}📋 Current subscription: $current_sub${NC}"

# Load environment variables to check subscription
if [ -f "../.env" ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
    if [ "$current_sub" != "$AZ_SUBSCRIPTION_ID" ]; then
        echo -e "${YELLOW}⚠️  Current subscription doesn't match .env file${NC}"
        echo -e "${YELLOW}🔄 Setting subscription to: $AZ_SUBSCRIPTION_ID${NC}"
        az account set --subscription $AZ_SUBSCRIPTION_ID
    fi
fi

# Step 3: Validate Bicep template
echo -e "\n${YELLOW}🔍 Step 3: Validating Bicep template${NC}"
az bicep build --file main.bicep
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Bicep template is valid${NC}"
else
    echo -e "${RED}❌ Bicep template validation failed${NC}"
    exit 1
fi

# Step 4: Deploy infrastructure
echo -e "\n${YELLOW}🚀 Step 4: Deploying Azure infrastructure${NC}"
echo -e "${YELLOW}⚠️  This will create Azure resources and may incur costs${NC}"
read -p "Do you want to proceed with deployment? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./deploy.sh
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Infrastructure deployment completed${NC}"
    else
        echo -e "${RED}❌ Infrastructure deployment failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⏭️  Skipping deployment${NC}"
    exit 0
fi

# Step 5: Run validation tests
echo -e "\n${YELLOW}🧪 Step 5: Running validation tests${NC}"
./test-resources.sh
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All validation tests passed${NC}"
else
    echo -e "${RED}❌ Some validation tests failed${NC}"
    echo -e "${YELLOW}⚠️  Please check the Azure portal and fix any issues${NC}"
fi

# Step 6: Next steps
echo -e "\n${BLUE}🎉 Setup Complete!${NC}"
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo -e "  1. Review the updated .env file (.env.updated)"
echo -e "  2. Deploy the Function App code for Confluence data ingestion"
echo -e "  3. Set up Azure OpenAI model deployments"
echo -e "  4. Test Confluence API connectivity"
echo -e "  5. Deploy the embedding and indexing pipeline"

echo -e "\n${GREEN}🚀 Your Confluence Q&A infrastructure is ready!${NC}" 