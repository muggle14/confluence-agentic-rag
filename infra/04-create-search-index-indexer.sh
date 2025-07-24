#!/bin/bash

# =============================================================================
# Script: create-search-resources.sh
# Purpose: Creates Azure AI Search index and indexer for Confluence knowledge graph
# 
# Description:
#   This script consolidates the creation of both search index and indexer into
#   a single operation. It creates a vector-enabled search index with appropriate
#   field mappings and then sets up an indexer to populate it from blob storage.
#
# Prerequisites:
#   - Azure CLI installed and authenticated
#   - Azure AI Search service deployed
#   - Blob data source already created
#   - Skillset already created (for enrichment pipeline)
#
# Environment Variables Required:
#   - None (uses hardcoded values for now, can be parameterized)
#
# Input Parameters:
#   $1 - Operation mode (optional): "index", "indexer", or "all" (default: "all")
#   $2 - Resource group name (optional, default: "rg-rag-confluence")
#   $3 - Search service name (optional, default: "srch-rag-conf")
#
# Output:
#   - Creates search index named "confluence-graph-embeddings"
#   - Creates indexer named "confluence-graph-indexer"
#   - Prints status messages to stdout
#   - Returns 0 on success, 1 on failure
#
# Example Usage:
#   ./create-search-resources.sh                    # Create both index and indexer
#   ./create-search-resources.sh index             # Create only index
#   ./create-search-resources.sh indexer           # Create only indexer
#   ./create-search-resources.sh all rg-prod srch-prod  # Use custom resource group and service
# =============================================================================

set -e  # Exit on error

# Default values
OPERATION_MODE="${1:-all}"
RESOURCE_GROUP="${2:-rg-rag-confluence}"
SEARCH_SERVICE="${3:-srch-rag-conf}"

# Constants
INDEX_NAME="confluence-graph-embeddings"
INDEXER_NAME="confluence-graph-indexer"
DATASOURCE_NAME="confluence-blob-datasource"
SKILLSET_NAME="confluence-graph-skillset"
API_VERSION="2023-11-01"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Function: print_status
# Purpose: Print colored status messages
# Input: $1 - Status type (info/success/error), $2 - Message
# Output: Colored message to stdout
# =============================================================================
print_status() {
    case $1 in
        "info")
            echo -e "${BLUE}[INFO]${NC} $2"
            ;;
        "success")
            echo -e "${GREEN}[SUCCESS]${NC} $2"
            ;;
        "error")
            echo -e "${RED}[ERROR]${NC} $2"
            ;;
    esac
}

# =============================================================================
# Function: check_prerequisites
# Purpose: Verify all required tools and services are available
# Input: None
# Output: Returns 0 if all prerequisites met, 1 otherwise
# =============================================================================
check_prerequisites() {
    print_status "info" "Checking prerequisites..."
    
    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        print_status "error" "Azure CLI is not installed"
        return 1
    fi
    
    # Check if logged in to Azure
    if ! az account show &> /dev/null; then
        print_status "error" "Not logged in to Azure. Run 'az login' first"
        return 1
    fi
    
    # Check if resource group exists
    if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        print_status "error" "Resource group '$RESOURCE_GROUP' does not exist"
        return 1
    fi
    
    # Check if search service exists
    if ! az search service show --name "$SEARCH_SERVICE" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
        print_status "error" "Search service '$SEARCH_SERVICE' does not exist in resource group '$RESOURCE_GROUP'"
        return 1
    fi
    
    print_status "success" "All prerequisites met"
    return 0
}

# =============================================================================
# Function: get_search_key
# Purpose: Retrieve the admin key for the search service
# Input: None (uses global variables)
# Output: Sets SEARCH_ADMIN_KEY variable
# =============================================================================
get_search_key() {
    print_status "info" "Retrieving search service admin key..."
    SEARCH_ADMIN_KEY=$(az search admin-key show \
        --service-name "$SEARCH_SERVICE" \
        --resource-group "$RESOURCE_GROUP" \
        --query primaryKey -o tsv)
    
    if [ -z "$SEARCH_ADMIN_KEY" ]; then
        print_status "error" "Failed to retrieve search service admin key"
        return 1
    fi
    
    print_status "success" "Admin key retrieved successfully"
    return 0
}

# =============================================================================
# Function: create_index
# Purpose: Create the search index with vector fields
# Input: None (uses global variables)
# Output: Creates search index in Azure AI Search
# =============================================================================
create_index() {
    print_status "info" "Creating search index '$INDEX_NAME'..."
    
    # Define the index schema
    local INDEX_SCHEMA='{
  "name": "'$INDEX_NAME'",
  "fields": [
    {
      "name": "id",
      "type": "Edm.String",
      "key": true,
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "page_id",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true
    },
    {
      "name": "title",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true,
      "retrievable": true,
      "analyzer": "standard.lucene"
    },
    {
      "name": "content",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "retrievable": true,
      "analyzer": "standard.lucene"
    },
    {
      "name": "space_key",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "facetable": true
    },
    {
      "name": "contentVector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile"
    },
    {
      "name": "titleVector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "dimensions": 1536,
      "vectorSearchProfile": "vector-profile"
    }
  ],
  "vectorSearch": {
    "algorithms": [
      {
        "name": "hnsw-algorithm",
        "kind": "hnsw",
        "hnswParameters": {
          "metric": "cosine",
          "m": 4,
          "efConstruction": 400,
          "efSearch": 500
        }
      }
    ],
    "profiles": [
      {
        "name": "vector-profile",
        "algorithm": "hnsw-algorithm"
      }
    ]
  }
}'

    # Create the index
    local RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT \
        "https://${SEARCH_SERVICE}.search.windows.net/indexes/${INDEX_NAME}?api-version=${API_VERSION}" \
        -H "api-key: $SEARCH_ADMIN_KEY" \
        -H "Content-Type: application/json" \
        -d "$INDEX_SCHEMA")
    
    local HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    local BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" -eq 201 ] || [ "$HTTP_CODE" -eq 204 ]; then
        print_status "success" "Index '$INDEX_NAME' created successfully"
        return 0
    else
        print_status "error" "Failed to create index. HTTP Code: $HTTP_CODE"
        print_status "error" "Response: $BODY"
        return 1
    fi
}

# =============================================================================
# Function: create_indexer
# Purpose: Create the indexer to populate the search index
# Input: None (uses global variables)
# Output: Creates indexer in Azure AI Search
# =============================================================================
create_indexer() {
    print_status "info" "Creating indexer '$INDEXER_NAME'..."
    
    # Define the indexer configuration
    local INDEXER_CONFIG='{
  "name": "'$INDEXER_NAME'",
  "dataSourceName": "'$DATASOURCE_NAME'",
  "skillsetName": "'$SKILLSET_NAME'",
  "targetIndexName": "'$INDEX_NAME'",
  "parameters": {
    "maxFailedItems": -1,
    "maxFailedItemsPerBatch": -1,
    "configuration": {
      "dataToExtract": "contentAndMetadata",
      "parsingMode": "json"
    }
  },
  "fieldMappings": [
    {
      "sourceFieldName": "metadata_storage_path",
      "targetFieldName": "id",
      "mappingFunction": {
        "name": "base64Encode"
      }
    },
    {
      "sourceFieldName": "id",
      "targetFieldName": "page_id"
    },
    {
      "sourceFieldName": "title",
      "targetFieldName": "title"
    },
    {
      "sourceFieldName": "body/storage/value",
      "targetFieldName": "content"
    },
    {
      "sourceFieldName": "space/key",
      "targetFieldName": "space_key"
    }
  ],
  "outputFieldMappings": [
    {
      "sourceFieldName": "/document/pages/*/contentVector",
      "targetFieldName": "contentVector"
    },
    {
      "sourceFieldName": "/document/titleVector",
      "targetFieldName": "titleVector"
    }
  ]
}'

    # Create the indexer
    local RESPONSE=$(curl -s -w "\n%{http_code}" -X PUT \
        "https://${SEARCH_SERVICE}.search.windows.net/indexers/${INDEXER_NAME}?api-version=${API_VERSION}" \
        -H "api-key: $SEARCH_ADMIN_KEY" \
        -H "Content-Type: application/json" \
        -d "$INDEXER_CONFIG")
    
    local HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    local BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" -eq 201 ] || [ "$HTTP_CODE" -eq 204 ]; then
        print_status "success" "Indexer '$INDEXER_NAME' created successfully"
        return 0
    else
        print_status "error" "Failed to create indexer. HTTP Code: $HTTP_CODE"
        print_status "error" "Response: $BODY"
        return 1
    fi
}

# =============================================================================
# Function: check_indexer_status
# Purpose: Check the status of the indexer
# Input: None (uses global variables)
# Output: Prints indexer status
# =============================================================================
check_indexer_status() {
    print_status "info" "Checking indexer status..."
    
    local RESPONSE=$(curl -s -X GET \
        "https://${SEARCH_SERVICE}.search.windows.net/indexers/${INDEXER_NAME}/status?api-version=${API_VERSION}" \
        -H "api-key: $SEARCH_ADMIN_KEY")
    
    echo "$RESPONSE" | jq '.'
}

# =============================================================================
# Main execution
# =============================================================================
main() {
    print_status "info" "Starting Azure AI Search resource creation..."
    print_status "info" "Operation mode: $OPERATION_MODE"
    print_status "info" "Resource group: $RESOURCE_GROUP"
    print_status "info" "Search service: $SEARCH_SERVICE"
    echo ""
    
    # Check prerequisites
    if ! check_prerequisites; then
        exit 1
    fi
    
    # Get search admin key
    if ! get_search_key; then
        exit 1
    fi
    
    # Execute based on operation mode
    case $OPERATION_MODE in
        "index")
            if create_index; then
                print_status "success" "Index creation completed successfully"
            else
                print_status "error" "Index creation failed"
                exit 1
            fi
            ;;
        "indexer")
            if create_indexer; then
                print_status "success" "Indexer creation completed successfully"
                check_indexer_status
            else
                print_status "error" "Indexer creation failed"
                exit 1
            fi
            ;;
        "all"|*)
            # Create index first
            if create_index; then
                echo ""
                # Then create indexer
                if create_indexer; then
                    print_status "success" "All resources created successfully"
                    echo ""
                    check_indexer_status
                else
                    print_status "error" "Indexer creation failed"
                    exit 1
                fi
            else
                print_status "error" "Index creation failed"
                exit 1
            fi
            ;;
    esac
    
    echo ""
    print_status "success" "Script execution completed"
}

# Run main function
main