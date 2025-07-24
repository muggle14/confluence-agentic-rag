#!/bin/bash

# Graph Recreation Workflow Script
# Updated: 2025-01-13

set -e  # Exit on error

# Parse command line arguments
CLEANUP_ONLY=false
RECREATE_ONLY=false
FULL_WORKFLOW=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --cleanup-only)
            CLEANUP_ONLY=true
            FULL_WORKFLOW=false
            ;;
        --recreate-only)
            RECREATE_ONLY=true
            FULL_WORKFLOW=false
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --cleanup-only    Only clean up the existing graph"
            echo "  --recreate-only   Only recreate the graph (skip cleanup)"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                 # Full workflow: cleanup + recreate + verify"
            echo "  $0 --cleanup-only  # Only delete existing graph"
            echo "  $0 --recreate-only # Only recreate graph (assumes clean state)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
    shift
done

echo "🔄 Confluence Graph Recreation Workflow"
echo "===================================="
echo "Updated: $(date)"
echo

# Stay in repo root (script should be run from project root)
# cd "$(dirname "$0")/.."  # REMOVED: This moves above project root, breaking paths

# Load environment variables
echo "📋 Loading environment variables..."
export $(grep -v '^#' notebooks/.env | grep -v '^$' | xargs)

# Verify key environment variables
if [ -z "$COSMOS_ENDPOINT" ]; then
    echo "❌ Error: COSMOS_ENDPOINT not set"
    exit 1
fi

echo "✅ Environment loaded"
echo "   Cosmos DB: $COSMOS_ENDPOINT"
echo "   Database: $COSMOS_DATABASE"
echo "   Container: $COSMOS_CONTAINER"
echo

# Determine workflow mode
if [ "$CLEANUP_ONLY" = true ]; then
    echo "🧹 CLEANUP ONLY MODE"
    echo "==================="
    
    echo "📌 Step 1: Cleaning up existing graph"
    echo "-------------------------------------"
    echo "Using Python: $(which python)"
    $(which python) -m notebooks.cleanup_graph --no-confirm
    
    if [ $? -eq 0 ]; then
        echo "✅ Graph cleanup completed successfully"
    else
        echo "❌ Graph cleanup failed"
        exit 1
    fi
    
    echo
    echo "🎉 Cleanup workflow completed!"
    echo "============================="
    echo "Completed: $(date)"
    exit 0
    
elif [ "$RECREATE_ONLY" = true ]; then
    echo "🔄 RECREATE ONLY MODE"
    echo "===================="
    
    echo "📌 Step 1: Running graph recreation with metrics"
    echo "------------------------------------------------"
    $(which python) -m notebooks.populate_graph --recreate --no-confirm
    
    if [ $? -eq 0 ]; then
        echo "✅ Graph recreation completed successfully"
    else
        echo "❌ Graph recreation failed"
        exit 1
    fi
    
else
    echo "🔄 FULL WORKFLOW MODE"
    echo "===================="
    
    echo "📌 Step 1: Cleaning up existing graph"
    echo "-------------------------------------"
    echo "Using Python: $(which python)"
    $(which python) -m notebooks.cleanup_graph --no-confirm
    
    if [ $? -eq 0 ]; then
        echo "✅ Graph cleanup completed successfully"
    else
        echo "❌ Graph cleanup failed"
        exit 1
    fi
    
    echo
    echo "📌 Step 2: Running graph recreation with metrics"
    echo "------------------------------------------------"
    $(which python) -m notebooks.populate_graph --recreate --no-confirm
    
    if [ $? -eq 0 ]; then
        echo "✅ Graph recreation completed successfully"
    else
        echo "❌ Graph recreation failed"
        exit 1
    fi
fi

# Wait for metrics computation to complete
echo
echo "⏳ Waiting for metrics computation to complete..."
sleep 10

# Step 3: Run metrics verification tests
echo
echo "📌 Step 3: Running metrics verification tests"
echo "--------------------------------------------"
$(which python) -m pytest notebooks/tests/graph_metrics_test.py -v

# Step 4: Query sample nodes to verify metrics
echo
echo "📌 Step 4: Verifying sample node metrics"
echo "----------------------------------------"
$(which python) -c "
from notebooks.config import GraphConfig
from common.graph_operations import GraphOperations

config = GraphConfig.from_environment()
ops = GraphOperations(config)
ops.connect()

# Query a sample page to check metrics
query = \"g.V().hasLabel('Page').limit(1).valueMap('id', 'title', 'hierarchy_depth', 'child_count', 'graph_centrality_score')\"
result = ops.client.submit(query).all().result()

if result:
    print('Sample node metrics:')
    for node in result:
        print(f\"  ID: {node.get('id', ['N/A'])[0]}\")
        print(f\"  Title: {node.get('title', ['N/A'])[0]}\")
        print(f\"  Hierarchy Depth: {node.get('hierarchy_depth', ['N/A'])[0]}\")
        print(f\"  Child Count: {node.get('child_count', ['N/A'])[0]}\")
        print(f\"  Centrality Score: {node.get('graph_centrality_score', ['N/A'])[0]}\")
else:
    print('No nodes found with metrics')

ops.disconnect()
"

echo
echo "🎉 Graph recreation workflow completed!"
echo "======================================"
echo "Completed: $(date)"