#!/bin/bash

# Confluence Q&A System - Modular Infrastructure Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Confluence Q&A System - Modular Infrastructure Deployment${NC}"
echo -e "${BLUE}============================================================${NC}"

# Load environment variables
if [ -f "../.env" ]; then
    echo -e "${YELLOW}📋 Loading environment variables from .env${NC}"
    set -a
    source ../.env
    set +a
else
    echo -e "${RED}❌ .env file not found. Please create one based on the template${NC}"
    exit 1
fi

# Check required environment variables
required_vars=("AZ_SUBSCRIPTION_ID" "AZ_RESOURCE_GROUP" "AZ_LOCATION" "STORAGE_ACCOUNT" "COSMOS_ACCOUNT" "SEARCH_SERVICE" "FUNC_APP" "CONFLUENCE_BASE" "CONFLUENCE_TOKEN" "CONFLUENCE_EMAIL")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ Required environment variable $var is not set${NC}"
        exit 1
    fi
done

echo -e "${YELLOW}🔐 Setting Azure subscription${NC}"
az account set --subscription $AZ_SUBSCRIPTION_ID

echo -e "${YELLOW}📦 Creating resource group if it doesn't exist${NC}"
az group create --name $AZ_RESOURCE_GROUP --location $AZ_LOCATION --output none

# Function to check if resource exists
check_resource_exists() {
    local resource_type=$1
    local resource_name=$2
    local resource_group=$3
    
    case $resource_type in
        "storage")
            az storage account show --name $resource_name --resource-group $resource_group --output none 2>/dev/null
            ;;
        "cosmos")
            az cosmosdb show --name $resource_name --resource-group $resource_group --output none 2>/dev/null
            ;;
        "search")
            az search service show --name $resource_name --resource-group $resource_group --output none 2>/dev/null
            ;;
        "functionapp")
            az functionapp show --name $resource_name --resource-group $resource_group --output none 2>/dev/null
            ;;
        *)
            return 1
            ;;
    esac
}

# Function to deploy a module
deploy_module() {
    local module_name=$1
    local resource_name=$2
    local resource_type=$3
    
    echo -e "\n${YELLOW}🔍 Checking if $module_name ($resource_name) exists...${NC}"
    
    if check_resource_exists $resource_type $resource_name $AZ_RESOURCE_GROUP; then
        echo -e "${GREEN}✅ $module_name already exists, skipping deployment${NC}"
        return 0
    else
        echo -e "${YELLOW}🚀 Deploying $module_name...${NC}"
        
        # Deploy the module (replace spaces with hyphens)
        deployment_name="$(echo $module_name | tr ' ' '-')-$(date +%s)"
        
        case $module_name in
            "Storage Account")
                az deployment group create \
                    --resource-group $AZ_RESOURCE_GROUP \
                    --name $deployment_name \
                    --template-file modules/storage.bicep \
                    --parameters storageAccountName=$STORAGE_ACCOUNT \
                    --output table
                ;;
            "Cosmos DB")
                az deployment group create \
                    --resource-group $AZ_RESOURCE_GROUP \
                    --name $deployment_name \
                    --template-file modules/cosmos.bicep \
                    --parameters cosmosAccountName=$COSMOS_ACCOUNT \
                    --output table
                ;;
            "Azure AI Search")
                az deployment group create \
                    --resource-group $AZ_RESOURCE_GROUP \
                    --name $deployment_name \
                    --template-file modules/search.bicep \
                    --parameters searchServiceName=$SEARCH_SERVICE \
                    --output table
                ;;
            "Function App")
                az deployment group create \
                    --resource-group $AZ_RESOURCE_GROUP \
                    --name $deployment_name \
                    --template-file modules/function-app.bicep \
                    --parameters \
                        functionAppName=$FUNC_APP \
                        storageAccountName=$STORAGE_ACCOUNT \
                        storageAccountKey=$STORAGE_KEY \
                        cosmosAccountName=$COSMOS_ACCOUNT \
                        cosmosKey=$COSMOS_KEY \
                        searchServiceName=$SEARCH_SERVICE \
                        searchKey=$SEARCH_KEY \
                        confluenceBase=$CONFLUENCE_BASE \
                        confluenceToken=$CONFLUENCE_TOKEN \
                        confluenceEmail=$CONFLUENCE_EMAIL \
                    --output table
                ;;
        esac
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ $module_name deployed successfully${NC}"
        else
            echo -e "${RED}❌ $module_name deployment failed${NC}"
            return 1
        fi
    fi
}

# Deploy resources incrementally
echo -e "\n${BLUE}📦 Starting incremental resource deployment...${NC}"

# 1. Deploy Storage Account
deploy_module "Storage Account" $STORAGE_ACCOUNT "storage"

# 2. Deploy Cosmos DB
deploy_module "Cosmos DB" $COSMOS_ACCOUNT "cosmos"

# 3. Deploy Azure AI Search
deploy_module "Azure AI Search" $SEARCH_SERVICE "search"

# 4. Deploy Function App
deploy_module "Function App" $FUNC_APP "functionapp"

echo -e "\n${BLUE}ℹ️  Skipping Azure OpenAI - using direct OpenAI API instead${NC}"

# Extract all deployment outputs and create updated .env file
echo -e "\n${YELLOW}📝 Extracting deployment outputs...${NC}"

# Get resource keys and endpoints
if check_resource_exists "storage" $STORAGE_ACCOUNT $AZ_RESOURCE_GROUP; then
    echo -e "${YELLOW}🔑 Getting Storage Account key...${NC}"
    STORAGE_KEY=$(az storage account keys list --account-name $STORAGE_ACCOUNT --resource-group $AZ_RESOURCE_GROUP --query '[0].value' -o tsv)
fi

if check_resource_exists "cosmos" $COSMOS_ACCOUNT $AZ_RESOURCE_GROUP; then
    echo -e "${YELLOW}🔑 Getting Cosmos DB key...${NC}"
    COSMOS_KEY=$(az cosmosdb keys list --name $COSMOS_ACCOUNT --resource-group $AZ_RESOURCE_GROUP --query 'primaryMasterKey' -o tsv)
fi

if check_resource_exists "search" $SEARCH_SERVICE $AZ_RESOURCE_GROUP; then
    echo -e "${YELLOW}🔑 Getting Search Service key...${NC}"
    SEARCH_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $AZ_RESOURCE_GROUP --query 'primaryKey' -o tsv)
fi

echo -e "${YELLOW}🔑 Using direct OpenAI API - no Azure OpenAI setup needed${NC}"

# Create updated .env file
echo -e "${YELLOW}📋 Creating updated .env file...${NC}"

cat > ../.env.updated << EOF
# Azure Subscription details
AZ_SUBSCRIPTION_ID=$AZ_SUBSCRIPTION_ID
AZ_RESOURCE_GROUP=$AZ_RESOURCE_GROUP
AZ_LOCATION=$AZ_LOCATION

# Cosmos DB
COSMOS_ACCOUNT=$COSMOS_ACCOUNT
COSMOS_KEY=$COSMOS_KEY
COSMOS_DB=confluence
COSMOS_GRAPH=pages

# Storage
STORAGE_ACCOUNT=$STORAGE_ACCOUNT
STORAGE_KEY=$STORAGE_KEY

# Azure AI Search
SEARCH_SERVICE=$SEARCH_SERVICE
SEARCH_INDEX=confluence-idx
SEARCH_KEY=$SEARCH_KEY

# OpenAI API (Direct)
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_EMBED_MODEL=text-embedding-3-large
OPENAI_CHAT_MODEL=gpt-4o

# Function App
FUNC_APP=$FUNC_APP

# Confluence
CONFLUENCE_BASE=$CONFLUENCE_BASE
CONFLUENCE_TOKEN=$CONFLUENCE_TOKEN
CONFLUENCE_EMAIL=$CONFLUENCE_EMAIL
EOF

echo -e "${GREEN}✅ Updated environment variables saved to .env.updated${NC}"

# Summary
echo -e "\n${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}===================${NC}"

resources=("Storage Account:$STORAGE_ACCOUNT:storage" "Cosmos DB:$COSMOS_ACCOUNT:cosmos" "Azure AI Search:$SEARCH_SERVICE:search" "Function App:$FUNC_APP:functionapp")

for resource_info in "${resources[@]}"; do
    IFS=':' read -r resource_name resource_id resource_type <<< "$resource_info"
    if check_resource_exists $resource_type $resource_id $AZ_RESOURCE_GROUP; then
        echo -e "${GREEN}✅ $resource_name: $resource_id${NC}"
    else
        echo -e "${RED}❌ $resource_name: $resource_id (failed)${NC}"
    fi
done

echo -e "\n${GREEN}🎉 Modular infrastructure deployment completed!${NC}"
echo -e "${YELLOW}📋 Next steps:${NC}"
echo -e "  1. Review the updated .env file (.env.updated)"
echo -e "  2. Run validation tests: ./test-resources.sh"
echo -e "  3. Deploy Function App and Web App components"
echo -e "  4. Test Confluence API connectivity"

echo -e "\n${BLUE}💡 To re-run this script safely, existing resources will be skipped${NC}" 