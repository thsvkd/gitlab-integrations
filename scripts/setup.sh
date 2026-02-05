#!/bin/bash
# GitLab-Slack Integration setup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

VENV_DIR=".venv"
PYTHON_VERSION="3.10"

echo "🚀 Starting GitLab-Slack Integration setup"
echo "================================================"

# Check Python version
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "❌ Python is not installed."
        echo "   Please install Python ${PYTHON_VERSION} or higher."
        exit 1
    fi

    # Check version
    CURRENT_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "✅ Python version: $CURRENT_VERSION"
}

# Create virtual environment
create_venv() {
    if [ -d "$VENV_DIR" ]; then
        echo "⚠️  Virtual environment already exists: $VENV_DIR"
        read -p "   Recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🗑️  Removing existing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            echo "   Using existing virtual environment."
            return
        fi
    fi

    echo "📦 Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "✅ Virtual environment created: $VENV_DIR"
}

# Activate virtual environment and install packages
install_packages() {
    echo "📥 Installing packages..."

    # Activate virtual environment
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    pip install --upgrade pip

    # Install packages
    pip install -e ".[dev]"

    echo "✅ Packages installed"
}

# Check .env file
check_env() {
    if [ ! -f ".env" ]; then
        echo "⚠️  .env file not found."
        if [ -f ".env.example" ]; then
            echo "   Copying .env.example to .env"
            cp .env.example .env
            echo "   Please edit .env file to set required values."
        else
            echo "   Creating .env file with default values."
            cat > .env << 'EOF'
# GitLab settings
GITLAB_URL=https://your-gitlab-url.com
GITLAB_TOKEN=your-gitlab-token
GITLAB_PROJECT_ID=1
GITLAB_WEBHOOK_SECRET=your-webhook-secret

# Slack settings
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_CHANNEL_ID=your-channel-id

# Server settings
HOST=0.0.0.0
PORT=8000
EOF
            echo "   .env file created. Please update the values."
        fi
    else
        echo "✅ .env file found"
    fi
}

# Main execution
main() {
    check_python
    create_venv
    install_packages
    check_env

    echo ""
    echo "================================================"
    echo "✅ Setup complete!"
    echo ""
    echo "📌 Usage:"
    echo "   Run server:              ./scripts/run.sh"
    echo "   Run on different port:   ./scripts/run.sh --port 9000"
    echo "================================================"
}

main
