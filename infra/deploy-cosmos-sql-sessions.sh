#!/bin/bash

# Deploy Cosmos DB SQL API for Session Storage
# This creates a separate Cosmos account optimized for session storage

set -e  # Exit on error

# Configuration
RESOURCE_GROUP="rg-rag-confluence"
DEPLOYMENT_NAME="cosmos-sql-sessions-$(date +%Y%m%d-%H%M%S)"
COSMOS_ACCOUNT_NAME="cosmosragsessions2"  # Must be globally unique, lowercase, no hyphens
LOCATION="eastus"

echo "🚀 Deploying Cosmos DB SQL API for Session Storage"
echo "=================================================="
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Cosmos Account: $COSMOS_ACCOUNT_NAME"
echo "  Location: $LOCATION"
echo "  Deployment: $DEPLOYMENT_NAME"
echo ""

# Check if resource group exists
echo "📦 Checking resource group..."
if ! az group show --name $RESOURCE_GROUP &>/dev/null; then
    echo "❌ Resource group $RESOURCE_GROUP does not exist"
    echo "   Run: az group create --name $RESOURCE_GROUP --location $LOCATION"
    exit 1
fi
echo "✅ Resource group exists"

# Deploy Cosmos SQL
echo ""
echo "🚀 Deploying Cosmos DB SQL API..."
az deployment group create \
    --resource-group $RESOURCE_GROUP \
    --name $DEPLOYMENT_NAME \
    --template-file modules/cosmos-sql.bicep \
    --parameters \
        cosmosAccountName=$COSMOS_ACCOUNT_NAME \
        location=$LOCATION \
        databaseName='rag-sessions' \
        containerName='sessions' \
        throughput=400 \
    --output json > deployment-output.json

if [ $? -ne 0 ]; then
    echo "❌ Deployment failed"
    exit 1
fi

echo "✅ Deployment successful"

# Extract outputs
echo ""
echo "📝 Extracting deployment outputs..."

COSMOS_ENDPOINT=$(az deployment group show \
    --resource-group $RESOURCE_GROUP \
    --name $DEPLOYMENT_NAME \
    --query properties.outputs.cosmosEndpoint.value \
    --output tsv)

COSMOS_KEY=$(az deployment group show \
    --resource-group $RESOURCE_GROUP \
    --name $DEPLOYMENT_NAME \
    --query properties.outputs.cosmosKey.value \
    --output tsv)

COSMOS_DB=$(az deployment group show \
    --resource-group $RESOURCE_GROUP \
    --name $DEPLOYMENT_NAME \
    --query properties.outputs.cosmosDatabaseName.value \
    --output tsv)

COSMOS_CONTAINER=$(az deployment group show \
    --resource-group $RESOURCE_GROUP \
    --name $DEPLOYMENT_NAME \
    --query properties.outputs.cosmosContainerName.value \
    --output tsv)

# Create or update .env file
ENV_FILE="../.env.sessions"

echo ""
echo "📝 Creating $ENV_FILE with connection details..."

cat > $ENV_FILE << EOF
# Cosmos DB SQL API (Session Storage)
# Generated: $(date)
# Deployment: $DEPLOYMENT_NAME

# SQL API Endpoints (for session storage)
COSMOS_SQL_ENDPOINT=$COSMOS_ENDPOINT
COSMOS_SQL_KEY=$COSMOS_KEY
COSMOS_SQL_DATABASE=$COSMOS_DB
COSMOS_SQL_CONTAINER=$COSMOS_CONTAINER
COSMOS_SQL_ACCOUNT=$COSMOS_ACCOUNT_NAME

# For backward compatibility with SessionStore
COSMOS_URL=$COSMOS_ENDPOINT
COSMOS_KEY=$COSMOS_KEY
COSMOS_DATABASE=$COSMOS_DB
COSMOS_SESSION_CONTAINER=$COSMOS_CONTAINER
EOF

echo "✅ Configuration saved to $ENV_FILE"

# Display summary
echo ""
echo "=================================================="
echo "✅ Cosmos DB SQL API Deployed Successfully!"
echo "=================================================="
echo ""
echo "📊 Deployment Summary:"
echo "  Account: $COSMOS_ACCOUNT_NAME"
echo "  Endpoint: $COSMOS_ENDPOINT"
echo "  Database: $COSMOS_DB"
echo "  Container: $COSMOS_CONTAINER"
echo ""
echo "📝 Next Steps:"
echo "  1. Copy the environment variables to your main .env file:"
echo "     cat $ENV_FILE >> ../.env"
echo ""
echo "  2. Test the connection:"
echo "     python ../tests/test_session_memory.py"
echo ""
echo "💰 Cost Information:"
echo "  - Serverless mode: Pay per request (no fixed cost)"
echo "  - Estimated: ~$0.25 per million operations"
echo ""
echo "🔗 Azure Portal:"
echo "  https://portal.azure.com/#resource/subscriptions/<your-sub-id>/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.DocumentDB/databaseAccounts/$COSMOS_ACCOUNT_NAME"
echo ""

# Clean up temporary file
rm -f deployment-output.json

echo "✅ Done!"