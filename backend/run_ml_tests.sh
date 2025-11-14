#!/bin/bash

# ML Test Runner Script for EcoStudio
# This script runs the ML module tests with various options

set -e  # Exit on error

echo "================================"
echo "EcoStudio ML Test Runner"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
VERBOSE=false
COVERAGE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            TEST_TYPE="unit"
            shift
            ;;
        --integration)
            TEST_TYPE="integration"
            shift
            ;;
        --features)
            TEST_TYPE="features"
            shift
            ;;
        --quick)
            TEST_TYPE="quick"
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./run_ml_tests.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --unit         Run only unit tests"
            echo "  --integration  Run only integration tests"
            echo "  --features     Run only feature engineering tests"
            echo "  --quick        Run quick tests (exclude slow tests)"
            echo "  -v, --verbose  Verbose output"
            echo "  --coverage     Generate coverage report"
            echo "  -h, --help     Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_ml_tests.sh                    # Run all tests"
            echo "  ./run_ml_tests.sh --unit             # Run unit tests only"
            echo "  ./run_ml_tests.sh --coverage         # Run with coverage"
            echo "  ./run_ml_tests.sh --quick -v         # Quick tests, verbose"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest"

# Add test selection
case $TEST_TYPE in
    unit)
        echo -e "${YELLOW}Running unit tests only...${NC}"
        PYTEST_CMD="$PYTEST_CMD -m unit tests/ml"
        ;;
    integration)
        echo -e "${YELLOW}Running integration tests only...${NC}"
        PYTEST_CMD="$PYTEST_CMD tests/ml/integration"
        ;;
    features)
        echo -e "${YELLOW}Running feature engineering tests only...${NC}"
        PYTEST_CMD="$PYTEST_CMD tests/ml/features"
        ;;
    quick)
        echo -e "${YELLOW}Running quick tests (excluding slow tests)...${NC}"
        PYTEST_CMD="$PYTEST_CMD -m 'not slow' tests/ml"
        ;;
    all)
        echo -e "${YELLOW}Running all ML tests...${NC}"
        PYTEST_CMD="$PYTEST_CMD tests/ml"
        ;;
esac

# Add verbose flag
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -vv"
fi

# Add coverage
if [ "$COVERAGE" = true ]; then
    echo -e "${YELLOW}Generating coverage report...${NC}"
    PYTEST_CMD="$PYTEST_CMD --cov=app/ml --cov-report=html --cov-report=term-missing"
fi

# Run the tests
echo ""
echo "Executing: $PYTEST_CMD"
echo ""

if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"

    if [ "$COVERAGE" = true ]; then
        echo ""
        echo -e "${GREEN}Coverage report generated at: htmlcov/index.html${NC}"
    fi

    exit 0
else
    echo ""
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
