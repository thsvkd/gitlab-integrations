#!/bin/bash
# GitLab Integrations run script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

VENV_DIR=".venv"

# Check virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found. Please run setup.sh first."
    echo "   ./scripts/setup.sh"
    exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Check .env file and load
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Please configure environment variables."
    exit 1
fi

# Read HOST, PORT from .env
source <(grep -E '^(HOST|PORT)=' .env | sed 's/^/export /')
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

echo "🚀 Starting GitLab Integrations server"
echo "================================================"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "================================================"

# Use HOST, PORT from .env if no arguments provided
if [ $# -eq 0 ]; then
    exec python -m gitlab_integrations.main --host "$HOST" --port "$PORT"
else
    # Pass arguments as-is
    exec python -m gitlab_integrations.main "$@"
fi
