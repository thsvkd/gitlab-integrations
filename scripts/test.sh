#!/bin/bash
# GitLab Integrations test script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

VENV_DIR=".venv"

# Check virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Please run setup.sh first."
    echo "   ./scripts/setup.sh"
    exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

echo "Running GitLab Integrations tests"
echo "================================================"

# Default options
VERBOSE=""
COVERAGE=""
SPECIFIC_TEST=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -vv)
            VERBOSE="-vv"
            shift
            ;;
        --cov|--coverage)
            COVERAGE="--cov=src/gitlab_integrations --cov-report=term-missing"
            shift
            ;;
        --html)
            COVERAGE="--cov=src/gitlab_integrations --cov-report=html"
            shift
            ;;
        -h|--help)
            echo "Usage: ./scripts/test.sh [options] [test_file]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose     Verbose output"
            echo "  -vv               More verbose output"
            echo "  --cov, --coverage Run with coverage report"
            echo "  --html            Generate HTML coverage report"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./scripts/test.sh                    Run all tests"
            echo "  ./scripts/test.sh -v                 Run with verbose output"
            echo "  ./scripts/test.sh --cov              Run with coverage"
            echo "  ./scripts/test.sh tests/test_webhooks.py  Run specific test file"
            exit 0
            ;;
        *)
            SPECIFIC_TEST="$1"
            shift
            ;;
    esac
done

# Build pytest command
CMD="pytest $VERBOSE $COVERAGE"

if [ -n "$SPECIFIC_TEST" ]; then
    CMD="$CMD $SPECIFIC_TEST"
else
    CMD="$CMD tests/"
fi

echo "Running: $CMD"
echo "================================================"

# Run tests
eval $CMD
EXIT_CODE=$?

echo "================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "All tests passed!"
else
    echo "Some tests failed."
fi

exit $EXIT_CODE
