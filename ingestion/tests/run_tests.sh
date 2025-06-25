#!/bin/bash

# Confluence Ingestion Pipeline - Test Runner
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Confluence Ingestion Pipeline - Test Runner${NC}"
echo -e "${BLUE}=============================================${NC}"

# Function to show usage
show_usage() {
    echo -e "\n${YELLOW}Usage:${NC}"
    echo -e "  $0 [test_type]"
    echo -e "\n${YELLOW}Available test types:${NC}"
    echo -e "  unit         - Run unit tests (no external dependencies)"
    echo -e "  integration  - Run integration tests (requires Azure & Confluence access)"
    echo -e "  all          - Run all tests"
    echo -e "  install      - Install test dependencies"
    echo -e "\n${YELLOW}Examples:${NC}"
    echo -e "  $0 unit"
    echo -e "  $0 integration"
    echo -e "  $0 all"
}

# Function to install dependencies
install_dependencies() {
    echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
    
    # Check if pip is available
    if ! command -v pip3 &> /dev/null; then
        echo -e "${RED}❌ pip3 not found. Please install Python 3 and pip.${NC}"
        exit 1
    fi
    
    # Install test dependencies
    pip3 install -r ../requirements.txt
    pip3 install pytest pytest-cov pytest-mock
    
    echo -e "${GREEN}✅ Dependencies installed successfully${NC}"
}

# Function to check environment for integration tests
check_integration_env() {
    echo -e "${YELLOW}🔍 Checking environment for integration tests...${NC}"
    
    required_vars=("CONFLUENCE_BASE" "CONFLUENCE_TOKEN" "CONFLUENCE_EMAIL" "STORAGE_CONN")
    missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Missing environment variables for integration tests:${NC}"
        for var in "${missing_vars[@]}"; do
            echo -e "   - $var"
        done
        echo -e "${YELLOW}💡 Integration tests will be skipped${NC}"
        return 1
    else
        echo -e "${GREEN}✅ Environment configured for integration tests${NC}"
        return 0
    fi
}

# Function to run unit tests
run_unit_tests() {
    echo -e "\n${BLUE}🔬 Running Unit Tests${NC}"
    echo -e "${BLUE}===================${NC}"
    
    if command -v pytest &> /dev/null; then
        # Use pytest if available
        pytest test_ingestion_unit.py -v --tb=short
    else
        # Fall back to unittest
        python3 test_ingestion_unit.py
    fi
    
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
    echo -e "\n${BLUE}🔗 Running Integration Tests${NC}"
    echo -e "${BLUE}===========================${NC}"
    
    if ! check_integration_env; then
        echo -e "${YELLOW}⏭️  Skipping integration tests due to missing environment${NC}"
        return 0
    fi
    
    if command -v pytest &> /dev/null; then
        # Use pytest if available
        pytest test_ingestion_integration.py -v --tb=short -s
    else
        # Fall back to unittest
        python3 test_ingestion_integration.py
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Integration tests passed${NC}"
        return 0
    else
        echo -e "${RED}❌ Integration tests failed${NC}"
        return 1
    fi
}

# Function to run all tests
run_all_tests() {
    echo -e "\n${BLUE}🚀 Running All Tests${NC}"
    echo -e "${BLUE}==================${NC}"
    
    unit_result=0
    integration_result=0
    
    # Run unit tests
    run_unit_tests
    unit_result=$?
    
    # Run integration tests
    run_integration_tests
    integration_result=$?
    
    # Summary
    echo -e "\n${BLUE}📊 Test Summary${NC}"
    echo -e "${BLUE}===============${NC}"
    
    if [ $unit_result -eq 0 ]; then
        echo -e "Unit Tests: ${GREEN}PASSED${NC}"
    else
        echo -e "Unit Tests: ${RED}FAILED${NC}"
    fi
    
    if [ $integration_result -eq 0 ]; then
        echo -e "Integration Tests: ${GREEN}PASSED${NC}"
    else
        echo -e "Integration Tests: ${RED}FAILED${NC}"
    fi
    
    # Overall result
    if [ $unit_result -eq 0 ] && [ $integration_result -eq 0 ]; then
        echo -e "\n${GREEN}🎉 All tests passed!${NC}"
        return 0
    else
        echo -e "\n${RED}❌ Some tests failed${NC}"
        return 1
    fi
}

# Main execution
if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

test_type=$1

case $test_type in
    "unit")
        run_unit_tests
        ;;
    "integration")
        run_integration_tests
        ;;
    "all")
        run_all_tests
        ;;
    "install")
        install_dependencies
        ;;
    *)
        echo -e "${RED}❌ Unknown test type: $test_type${NC}"
        show_usage
        exit 1
        ;;
esac 