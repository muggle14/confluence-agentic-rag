#!/bin/bash

# Deploy Graph Enrichment Function for Azure AI Search Integration
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Graph Enrichment Function${NC}"
echo -e "${BLUE}====================================${NC}"

# Configuration
RESOURCE_GROUP="rg-rag-confluence"
# Keep Function dedicated to graph enrichment to avoid name collision
FUNCTION_APP="func-rag-graph-enrich"
COSMOS_ACCOUNT="cosmos-rag-conf"

# Get Cosmos DB connection details
echo -e "${YELLOW}🔑 Retrieving Cosmos DB connection details...${NC}"
COSMOS_ENDPOINT="https://${COSMOS_ACCOUNT}.documents.azure.com/"
COSMOS_KEY=$(az cosmosdb keys list --name $COSMOS_ACCOUNT --resource-group $RESOURCE_GROUP --query primaryMasterKey -o tsv)

# Exit early if az returns empty key
if [[ -z "$COSMOS_KEY" ]]; then
    echo -e "${RED}❌ Could not fetch Cosmos key – check account & permissions${NC}"
    exit 1
fi

# Check if Function App exists
echo -e "${YELLOW}🔍 Checking Function App...${NC}"
if ! az functionapp show --name $FUNCTION_APP --resource-group $RESOURCE_GROUP &> /dev/null; then
    echo -e "${YELLOW}📦 Function App $FUNCTION_APP not found. Creating it now...${NC}"
    
    # Get storage account key
    STORAGE_ACCOUNT="stgragconf"
    STORAGE_KEY=$(az storage account keys list --account-name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv)
    
    # Get search service details
    SEARCH_SERVICE="srch-rag-conf"
    SEARCH_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)
    
    # Create the Function App using bicep
    echo -e "${YELLOW}🚀 Creating Function App for graph enrichment...${NC}"
    az deployment group create \
        --resource-group $RESOURCE_GROUP \
        --name "graph-enrichment-function-$(date +%s)" \
        --template-file modules/function-app.bicep \
        --parameters \
            functionAppName=$FUNCTION_APP \
            storageAccountName=$STORAGE_ACCOUNT \
            storageAccountKey=$STORAGE_KEY \
            cosmosAccountName=$COSMOS_ACCOUNT \
            cosmosKey=$COSMOS_KEY \
            searchServiceName=$SEARCH_SERVICE \
            searchKey=$SEARCH_KEY \
            confluenceBase="https://placeholder.atlassian.net/wiki/rest/api" \
            confluenceToken="placeholder" \
            confluenceEmail="placeholder@example.com" \
        --output table
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to create Function App${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Function App created successfully${NC}"
    
    # Wait for Function App to be fully ready
    echo -e "${YELLOW}⏳ Waiting for Function App to be fully ready...${NC}"
    sleep 30
fi

# Navigate to project root
cd "$(dirname "$0")/.."

# Create temporary deployment directory
TEMP_DIR=$(mktemp -d)
echo -e "${YELLOW}📁 Creating deployment package in $TEMP_DIR${NC}"

# Copy graph enrichment function
echo -e "${YELLOW}📋 Copying graph enrichment function...${NC}"
mkdir -p "$TEMP_DIR/graph_enrichment_skill"
cp -r graph_enrichment_skill/* "$TEMP_DIR/graph_enrichment_skill/"

# Copy notebooks module (required by graph enrichment for GraphConfig)
echo -e "${YELLOW}📋 Copying notebooks module...${NC}"
# Include only what is imported → saves cold-start time
rsync -av --exclude="__pycache__" --exclude="*.pyc" --exclude="tests" --exclude="examples" notebooks "$TEMP_DIR/"

# Create host.json
echo -e "${YELLOW}📝 Creating host.json...${NC}"
cat > "$TEMP_DIR/host.json" << 'EOF'
{
  "version": "2.0",
  "functionTimeout": "00:05:00",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "excludedTypes": "Request"
      }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[3.*, 4.0.0)"
  },
  "extensions": {
    "http": {
      "routePrefix": "api",
      "maxOutstandingRequests": 200,
      "maxConcurrentRequests": 100
    }
  }
}
EOF

# Create requirements.txt combining all dependencies
echo -e "${YELLOW}📝 Creating combined requirements.txt...${NC}"
cat > "$TEMP_DIR/requirements.txt" << 'EOF'
# Azure Functions
azure-functions==1.19.0

# Cosmos DB / Gremlin
gremlinpython==3.6.2

# Environment management
python-dotenv==1.0.0

# Logging
python-json-logger==2.0.7
EOF

# Add local.settings.json for local development
cat > "$TEMP_DIR/local.settings.json" << EOF
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "COSMOS_ENDPOINT": "${COSMOS_ENDPOINT}",
    "COSMOS_KEY": "${COSMOS_KEY}",
    "COSMOS_DATABASE": "confluence-graph",
    "COSMOS_CONTAINER": "knowledge-graph"
  }
}
EOF

# Deploy to Azure
echo -e "${YELLOW}🚀 Deploying to Azure Function App...${NC}"
cd "$TEMP_DIR"

# Check if Azure Functions Core Tools is installed
if ! command -v func &> /dev/null; then
    echo -e "${YELLOW}📦 Installing functions via zip deploy...${NC}"
    
    # Build Python packages
    pip install -r requirements.txt -t .python_packages/lib/site-packages
    
    # Create zip file
    zip -r deployment.zip . -x "*.pyc" -x "__pycache__/*" -x ".venv/*"
    
    # Deploy using Azure CLI
    az functionapp deployment source config-zip \
        --resource-group $RESOURCE_GROUP \
        --name $FUNCTION_APP \
        --src deployment.zip
else
    # Use func publish (if installed) - use --build remote to avoid local pip issues
    echo -e "${YELLOW}📦 Using func tools with remote build...${NC}"
    func azure functionapp publish "$FUNCTION_APP" --python --build remote
fi

# Set environment variables
echo -e "${YELLOW}🔧 Setting environment variables...${NC}"
az functionapp config appsettings set \
    --name $FUNCTION_APP \
    --resource-group $RESOURCE_GROUP \
    --settings \
    "COSMOS_ENDPOINT=${COSMOS_ENDPOINT}" \
    "COSMOS_KEY=${COSMOS_KEY}" \
    "COSMOS_DATABASE=confluence-graph" \
    "COSMOS_CONTAINER=knowledge-graph" \
    --output none

# Clean up
cd - > /dev/null
rm -rf "$TEMP_DIR"

# Get function details
echo -e "\n${YELLOW}📋 Retrieving function details...${NC}"
FUNCTION_URL="https://${FUNCTION_APP}.azurewebsites.net/api/graph_enrichment_skill"
FUNCTION_KEY=$(az functionapp function keys list \
    --resource-group $RESOURCE_GROUP \
    --name $FUNCTION_APP \
    --function-name graph_enrichment_skill \
    --query "default" -o tsv 2>/dev/null || echo "")

echo -e "\n${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}===================${NC}"
echo -e "✅ Function App: $FUNCTION_APP"
echo -e "✅ Cosmos DB: Connected"

if [ -n "$FUNCTION_KEY" ]; then
    echo -e "\n${GREEN}📌 Function URL (with key):${NC}"
    echo -e "${YELLOW}${FUNCTION_URL}?code=${FUNCTION_KEY}${NC}"
    echo -e "\n${BLUE}Copy that value into the uri field of your skillset JSON:${NC}"
    echo -e "\"uri\": \"${FUNCTION_URL}?code=${FUNCTION_KEY}\""
else
    echo -e "\n${YELLOW}⚠️  Function key not available yet. Run this command after deployment:${NC}"
    echo -e "az functionapp function keys list --resource-group $RESOURCE_GROUP --name $FUNCTION_APP --function-name graph_enrichment_skill --query default -o tsv"
fi

# Test the function
echo -e "\n${YELLOW}🧪 Testing function endpoint...${NC}"
if [ -n "$FUNCTION_KEY" ]; then
    TEST_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$FUNCTION_URL" \
        -H "x-functions-key: $FUNCTION_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "values": [{
                "recordId": "test",
                "data": {
                    "page_id": "test123",
                    "title": "Test Page",
                    "space_key": "TEST"
                }
            }]
        }' | tail -n1)
    
    if [ "$TEST_RESPONSE" = "200" ]; then
        echo -e "${GREEN}✅ Function is responding correctly${NC}"
    else
        echo -e "${YELLOW}⚠️  Function returned status code: $TEST_RESPONSE${NC}"
        echo -e "${YELLOW}   Function may still be starting up${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Function key not available yet. Function is still initializing.${NC}"
fi

echo -e "\n${GREEN}🎉 Graph enrichment function deployed!${NC}"
echo -e "\n${YELLOW}📋 Next Steps:${NC}"
echo -e "1. Wait 2-3 minutes for function to fully initialize"
echo -e "2. Run the search deployment: ./deploy-graph-aware-search-integrated.sh"
echo -e "3. Monitor function logs: az functionapp logs tail --name $FUNCTION_APP --resource-group $RESOURCE_GROUP" 