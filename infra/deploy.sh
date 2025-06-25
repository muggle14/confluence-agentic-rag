#!/bin/bash

# Confluence Q&A System - Infrastructure Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Confluence Q&A System Infrastructure Deployment${NC}"

# Load environment variables
if [ -f "../.env" ]; then
    echo -e "${YELLOW}📋 Loading environment variables from .env${NC}"
    # Use a safer method to load environment variables
    set -a
    source ../.env
    set +a
else
    echo -e "${RED}❌ .env file not found. Please create one based on the infra-README.md${NC}"
    exit 1
fi

# Check required environment variables
required_vars=("AZ_SUBSCRIPTION_ID" "AZ_RESOURCE_GROUP" "AZ_LOCATION")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ Required environment variable $var is not set${NC}"
        exit 1
    fi
done

echo -e "${YELLOW}🔐 Setting Azure subscription${NC}"
az account set --subscription $AZ_SUBSCRIPTION_ID

echo -e "${YELLOW}📦 Creating resource group if it doesn't exist${NC}"
az group create --name $AZ_RESOURCE_GROUP --location $AZ_LOCATION

echo -e "${YELLOW}🔍 Validating Bicep template${NC}"
az deployment group validate \
    --resource-group $AZ_RESOURCE_GROUP \
    --template-file main.bicep \
    --parameters main.bicepparam

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Bicep template validation successful${NC}"
else
    echo -e "${RED}❌ Bicep template validation failed${NC}"
    exit 1
fi

echo -e "${YELLOW}🚀 Deploying Azure resources${NC}"
deployment_output=$(az deployment group create \
    --resource-group $AZ_RESOURCE_GROUP \
    --template-file main.bicep \
    --parameters main.bicepparam \
    --output json)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Azure resources deployed successfully${NC}"
    
    # Extract outputs
    echo -e "${YELLOW}📝 Extracting deployment outputs${NC}"
    echo "$deployment_output" > deployment-output.json
    
    # Update .env file with actual values
    echo -e "${YELLOW}📋 Updating .env file with deployment outputs${NC}"
    
    storage_key=$(echo "$deployment_output" | jq -r '.properties.outputs.storageAccountKey.value')
    cosmos_key=$(echo "$deployment_output" | jq -r '.properties.outputs.cosmosKey.value')
    search_key=$(echo "$deployment_output" | jq -r '.properties.outputs.searchServiceKey.value')
    aoai_key=$(echo "$deployment_output" | jq -r '.properties.outputs.aoaiKey.value')
    aoai_endpoint=$(echo "$deployment_output" | jq -r '.properties.outputs.aoaiEndpoint.value')
    
    # Create updated .env file
    cat > ../.env.updated << EOF
# Azure Subscription details
AZ_SUBSCRIPTION_ID=$AZ_SUBSCRIPTION_ID
AZ_RESOURCE_GROUP=$AZ_RESOURCE_GROUP
AZ_LOCATION=$AZ_LOCATION

# Cosmos DB
COSMOS_ACCOUNT=$COSMOS_ACCOUNT
COSMOS_KEY=$cosmos_key
COSMOS_DB=confluence
COSMOS_GRAPH=pages

# Storage
STORAGE_ACCOUNT=$STORAGE_ACCOUNT
STORAGE_KEY=$storage_key

# Azure AI Search
SEARCH_SERVICE=$SEARCH_SERVICE
SEARCH_INDEX=confluence-idx
SEARCH_KEY=$search_key

# Azure OpenAI
AOAI_RESOURCE=$AOAI_RESOURCE
AOAI_ENDPOINT=$aoai_endpoint
AOAI_KEY=$aoai_key
AOAI_EMBED_DEPLOY=text-embedding-3-large

# Function App
FUNC_APP=$FUNC_APP

# Confluence
CONFLUENCE_BASE=$CONFLUENCE_BASE
CONFLUENCE_TOKEN=$CONFLUENCE_TOKEN
CONFLUENCE_EMAIL=$CONFLUENCE_EMAIL
EOF

    echo -e "${GREEN}✅ Updated environment variables saved to .env.updated${NC}"
    echo -e "${YELLOW}📋 Please review and replace your .env file with .env.updated${NC}"
    
else
    echo -e "${RED}❌ Azure resources deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 Infrastructure deployment completed successfully!${NC}"
echo -e "${YELLOW}📋 Next steps:${NC}"
echo -e "  1. Review the updated .env file"
echo -e "  2. Run the validation tests"
echo -e "  3. Deploy the Function App code" 