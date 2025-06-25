#!/bin/bash

# Deploy Function App Code - Confluence Ingestion Pipeline
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Deploying Function App Code - Confluence Ingestion${NC}"
echo -e "${BLUE}=================================================${NC}"

# Load environment variables
if [ -f "../.env.updated" ]; then
    echo -e "${YELLOW}📋 Loading environment variables from .env.updated${NC}"
    set -a
    source ../.env.updated
    set +a
elif [ -f "../.env" ]; then
    echo -e "${YELLOW}📋 Loading environment variables from .env${NC}"
    set -a
    source ../.env
    set +a
else
    echo -e "${RED}❌ No environment file found${NC}"
    exit 1
fi

# Check required environment variables
required_vars=("FUNC_APP" "AZ_RESOURCE_GROUP")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ Required environment variable $var is not set${NC}"
        exit 1
    fi
done

# Check if Azure Functions Core Tools is installed
if ! command -v func &> /dev/null; then
    echo -e "${RED}❌ Azure Functions Core Tools not found${NC}"
    echo -e "${YELLOW}💡 Install with: npm install -g azure-functions-core-tools@4 --unsafe-perm true${NC}"
    exit 1
fi

# Check if the Function App exists
echo -e "${YELLOW}🔍 Checking if Function App exists...${NC}"
if ! az functionapp show --name $FUNC_APP --resource-group $AZ_RESOURCE_GROUP &> /dev/null; then
    echo -e "${RED}❌ Function App $FUNC_APP not found in resource group $AZ_RESOURCE_GROUP${NC}"
    echo -e "${YELLOW}💡 Please run the infrastructure deployment first: ./deploy-modular.sh${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Function App $FUNC_APP found${NC}"

# Navigate to the ingestion directory
INGESTION_DIR="../ingestion"
if [ ! -d "$INGESTION_DIR" ]; then
    echo -e "${RED}❌ Ingestion directory not found: $INGESTION_DIR${NC}"
    exit 1
fi

echo -e "${YELLOW}📁 Navigating to ingestion directory...${NC}"
cd "$INGESTION_DIR"

# Check if required files exist
required_files=("__init__.py" "function.json" "requirements.txt")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Required file not found: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ All required files found${NC}"

# Create host.json if it doesn't exist
if [ ! -f "host.json" ]; then
    echo -e "${YELLOW}📝 Creating host.json...${NC}"
    cat > host.json << 'EOF'
{
  "version": "2.0",
  "functionTimeout": "00:10:00",
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
  }
}
EOF
fi

# Deploy the function
echo -e "${YELLOW}🚀 Deploying function code to $FUNC_APP...${NC}"
echo -e "${YELLOW}⏳ This may take a few minutes...${NC}"

func azure functionapp publish $FUNC_APP --python

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Function code deployed successfully${NC}"
    
    # Get the function URL
    function_url="https://$FUNC_APP.azurewebsites.net"
    echo -e "${YELLOW}🔗 Function App URL: $function_url${NC}"
    
    # Test the function app accessibility
    echo -e "${YELLOW}🧪 Testing function app accessibility...${NC}"
    if curl -s -f "$function_url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Function App is accessible${NC}"
    else
        echo -e "${YELLOW}⚠️  Function App may still be starting up${NC}"
    fi
    
    echo -e "\n${BLUE}📋 Next Steps:${NC}"
    echo -e "  1. Monitor function execution in Azure Portal"
    echo -e "  2. Check Application Insights for logs"
    echo -e "  3. Verify data ingestion in Storage Account"
    echo -e "  4. Run integration tests: cd ../infra && ./run-tests.sh integration"
    
else
    echo -e "${RED}❌ Function code deployment failed${NC}"
    exit 1
fi

echo -e "\n${GREEN}🎉 Function App deployment completed!${NC}" 