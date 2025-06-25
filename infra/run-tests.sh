#!/bin/bash

# Confluence Q&A System - Modular Test Runner
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Confluence Q&A System - Test Runner${NC}"
echo -e "${BLUE}=======================================${NC}"

# Test modules available
AVAILABLE_TESTS=("storage" "cosmos" "search" "function-app" "confluence")

# Function to show usage
show_usage() {
    echo -e "\n${YELLOW}Usage:${NC}"
    echo -e "  $0 [test_name]"
    echo -e "\n${YELLOW}Available tests:${NC}"
    echo -e "  all        - Run all tests"
    echo -e "  storage      - Test Storage Account"
    echo -e "  cosmos       - Test Cosmos DB"
    echo -e "  search       - Test Azure AI Search"
    echo -e "  function-app - Test Function App"
    echo -e "  confluence   - Test Confluence API"
    echo -e "\n${YELLOW}Examples:${NC}"
    echo -e "  $0 all"
    echo -e "  $0 storage"
    echo -e "  $0 cosmos"
}

# Function to run a specific test
run_test_module() {
    local test_name=$1
    local test_script="tests/test-${test_name}.sh"
    
    if [ -f "$test_script" ]; then
        echo -e "\n${BLUE}🚀 Running $test_name tests...${NC}"
        chmod +x "$test_script"
        if ./"$test_script"; then
            echo -e "${GREEN}✅ $test_name tests completed successfully${NC}"
            return 0
        else
            echo -e "${RED}❌ $test_name tests failed${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ Test script not found: $test_script${NC}"
        return 1
    fi
}

# Function to run Confluence API test
run_confluence_test() {
    echo -e "\n${BLUE}🚀 Running Confluence API tests...${NC}"
    if python3 test-confluence-api.py; then
        echo -e "${GREEN}✅ Confluence API tests completed successfully${NC}"
        return 0
    else
        echo -e "${RED}❌ Confluence API tests failed${NC}"
        return 1
    fi
}

# Main execution
if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

test_to_run=$1
total_tests=0
passed_tests=0
failed_tests=0

case $test_to_run in
    "all")
        echo -e "${YELLOW}🔄 Running all tests...${NC}"
        
        # Run each test module
        for test in "${AVAILABLE_TESTS[@]}"; do
            ((total_tests++))
            if [ "$test" == "confluence" ]; then
                if run_confluence_test; then
                    ((passed_tests++))
                else
                    ((failed_tests++))
                fi
            else
                if run_test_module "$test"; then
                    ((passed_tests++))
                else
                    ((failed_tests++))
                fi
            fi
        done
        
        # Summary
        echo -e "\n${BLUE}📊 Overall Test Summary${NC}"
        echo -e "${BLUE}======================${NC}"
        echo -e "Total test modules: $total_tests"
        echo -e "Passed: ${GREEN}$passed_tests${NC}"
        echo -e "Failed: ${RED}$failed_tests${NC}"
        
        if [ $failed_tests -eq 0 ]; then
            echo -e "\n${GREEN}🎉 All tests passed! Infrastructure is ready.${NC}"
            exit 0
        else
            echo -e "\n${RED}❌ Some tests failed. Please check the output above.${NC}"
            exit 1
        fi
        ;;
    "confluence")
        run_confluence_test
        ;;
    "storage"|"cosmos"|"search"|"function-app")
        run_test_module "$test_to_run"
        ;;
    *)
        echo -e "${RED}❌ Unknown test: $test_to_run${NC}"
        show_usage
        exit 1
        ;;
esac 