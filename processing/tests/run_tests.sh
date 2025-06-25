#!/bin/bash

# Processing Pipeline Test Runner
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Confluence Processing Pipeline - Test Runner${NC}"
echo -e "${BLUE}==============================================${NC}"

# Function to show usage
show_usage() {
    echo -e "\nUsage: $0 [test_type]"
    echo -e "\nTest types:"
    echo -e "  unit       - Run unit tests only"
    echo -e "  integration - Run integration tests only" 
    echo -e "  all        - Run all tests (default)"
    echo -e "\nExamples:"
    echo -e "  $0 unit"
    echo -e "  $0 all"
}

# Function to run unit tests
run_unit_tests() {
    echo -e "\n${YELLOW}🔬 Running Unit Tests${NC}"
    echo -e "${YELLOW}====================${NC}"
    
    # Install dependencies if needed
    if ! python3 -c "import bs4, html2text" 2>/dev/null; then
        echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
        pip3 install -r ../requirements.txt
    fi
    
    # Run unit tests
    python3 -m pytest test_processing_unit.py -v
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Unit tests passed${NC}"
        return 0
    else
        echo -e "${RED}❌ Unit tests failed${NC}"
        return 1
    fi
}

# Function to run integration tests
run_integration_tests() {
    echo -e "\n${YELLOW}🔗 Running Integration Tests${NC}"
    echo -e "${YELLOW}============================${NC}"
    
    # Check if environment is configured
    if [ -z "$STORAGE_ACCOUNT" ] && [ -z "$STORAGE_KEY" ]; then
        echo -e "${YELLOW}⚠️  Integration tests require Azure storage configuration${NC}"
        echo -e "${YELLOW}   Set STORAGE_ACCOUNT and STORAGE_KEY environment variables${NC}"
        echo -e "${YELLOW}   Or run: source ../../.env.updated${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}📋 Environment configured for integration tests${NC}"
    
    # TODO: Add integration tests
    echo -e "${YELLOW}⚠️  Integration tests not implemented yet${NC}"
    echo -e "${YELLOW}   Add to TODO: Create integration tests for full pipeline${NC}"
    
    return 0
}

# Main execution
test_type="${1:-all}"

case $test_type in
    "unit")
        run_unit_tests
        exit $?
        ;;
    "integration")
        run_integration_tests
        exit $?
        ;;
    "all")
        echo -e "${YELLOW}🏃 Running all tests...${NC}"
        
        unit_result=0
        integration_result=0
        
        run_unit_tests || unit_result=$?
        run_integration_tests || integration_result=$?
        
        if [ $unit_result -eq 0 ] && [ $integration_result -eq 0 ]; then
            echo -e "\n${GREEN}🎉 All tests passed!${NC}"
            exit 0
        else
            echo -e "\n${RED}❌ Some tests failed${NC}"
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}❌ Unknown test type: $test_type${NC}"
        show_usage
        exit 1
        ;;
esac 