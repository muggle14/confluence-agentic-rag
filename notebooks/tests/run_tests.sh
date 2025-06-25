#!/bin/bash
# Test Runner for Graph Population Module

set -e

echo "🧪 Running Graph Population Module Tests"
echo "======================================"

# Set the PYTHONPATH to include the parent directory
export PYTHONPATH="$(dirname $(dirname $(dirname $(realpath $0)))):$PYTHONPATH"

# Change to the tests directory
cd "$(dirname "$0")"

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing..."
    pip install pytest pytest-asyncio
fi

# Run all tests with verbose output
echo "📋 Running all tests..."
pytest -v --tb=short

# Run specific test suites if requested
if [ "$1" = "models" ]; then
    echo "🔧 Running graph models tests..."
    pytest test_graph_models.py -v
elif [ "$1" = "operations" ]; then
    echo "🔗 Running graph operations tests..."
    pytest test_graph_operations.py -v
elif [ "$1" = "populate" ]; then
    echo "🚀 Running population tests..."
    pytest test_populate_graph.py -v
elif [ "$1" = "integration" ]; then
    echo "🔄 Running integration tests..."
    pytest test_integration.py -v
fi

echo "✅ Tests completed!" 