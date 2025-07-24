#!/bin/bash

# Graph Enrichment Integration Deployment Script
# This script runs both deployment steps for graph enrichment integration

set -e

echo "🚀 Starting Graph Enrichment Integration Deployment"
echo "================================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f "../.env" ] && [ ! -f ".env" ] && [ ! -f "../infra/.env" ]; then
    echo -e "${RED}❌ No .env file found. Please create one with required configuration${NC}"
    echo "Required variables:"
    echo "  - SEARCH_KEY"
    echo "  - AZURE_OPENAI_KEY" 
    echo "  - GRAPH_ENRICHMENT_FUNCTION_KEY (optional)"
    exit 1
fi

# Step 1: Deploy infrastructure
echo -e "\n${GREEN}📋 Step 1: Deploying Search Infrastructure${NC}"
echo "Creating index, skillset, and indexer..."
python3 01_deploy_graph_enriched_search.py

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Infrastructure deployment failed${NC}"
    exit 1
fi

# Ask user if they want to run the indexer
echo -e "\n${GREEN}✅ Infrastructure deployment completed successfully${NC}"
read -p "Do you want to run the indexer now? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Step 2: Run migration and verification
    echo -e "\n${GREEN}📋 Step 2: Running Migration and Verification${NC}"
    python3 02_migration_and_verification.py
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Migration failed${NC}"
        exit 1
    fi
    
    echo -e "\n${GREEN}✅ Deployment completed successfully!${NC}"
else
    echo -e "\n${GREEN}ℹ️ Infrastructure deployed. Run the following when ready:${NC}"
    echo "python3 02_migration_and_verification.py"
fi

echo -e "\n${GREEN}📚 Next Steps:${NC}"
echo "1. Verify the results in Azure Portal"
echo "2. Test search queries with graph-aware scoring"
echo "3. Update your application to use 'confluence-graph-embeddings-v2' index"