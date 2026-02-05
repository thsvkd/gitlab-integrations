#!/bin/bash
# GitLab-Slack Integration 환경 설정 스크립트

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
PYTHON_VERSION="3.11"

echo "🚀 GitLab-Slack Integration 환경 설정 시작"
echo "================================================"

# Python 버전 확인
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "❌ Python이 설치되어 있지 않습니다."
        echo "   Python ${PYTHON_VERSION} 이상을 설치해주세요."
        exit 1
    fi

    # 버전 확인
    CURRENT_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo "✅ Python 버전: $CURRENT_VERSION"
}

# 가상환경 생성
create_venv() {
    if [ -d "$VENV_DIR" ]; then
        echo "⚠️  가상환경이 이미 존재합니다: $VENV_DIR"
        read -p "   재생성하시겠습니까? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🗑️  기존 가상환경 삭제 중..."
            rm -rf "$VENV_DIR"
        else
            echo "   기존 가상환경을 사용합니다."
            return
        fi
    fi

    echo "📦 가상환경 생성 중..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "✅ 가상환경 생성 완료: $VENV_DIR"
}

# 가상환경 활성화 및 패키지 설치
install_packages() {
    echo "📥 패키지 설치 중..."
    
    # 가상환경 활성화
    source "$VENV_DIR/bin/activate"
    
    # pip 업그레이드
    pip install --upgrade pip
    
    # 패키지 설치
    pip install -e ".[dev]"
    
    echo "✅ 패키지 설치 완료"
}

# .env 파일 확인
check_env() {
    if [ ! -f ".env" ]; then
        echo "⚠️  .env 파일이 없습니다."
        if [ -f ".env.example" ]; then
            echo "   .env.example을 복사하여 .env 파일을 생성합니다."
            cp .env.example .env
            echo "   .env 파일을 편집하여 필요한 값을 설정해주세요."
        else
            echo "   .env 파일을 생성하고 필요한 환경 변수를 설정해주세요."
            cat > .env << 'EOF'
# GitLab 설정
GITLAB_URL=https://your-gitlab-url.com
GITLAB_TOKEN=your-gitlab-token
GITLAB_PROJECT_ID=1
GITLAB_WEBHOOK_SECRET=your-webhook-secret

# Slack 설정
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_CHANNEL_ID=your-channel-id

# 서버 설정
HOST=0.0.0.0
PORT=8000
EOF
            echo "   .env 파일이 생성되었습니다. 값을 수정해주세요."
        fi
    else
        echo "✅ .env 파일 확인됨"
    fi
}

# 메인 실행
main() {
    check_python
    create_venv
    install_packages
    check_env

    echo ""
    echo "================================================"
    echo "✅ 환경 설정 완료!"
    echo ""
    echo "📌 사용 방법:"
    echo "   가상환경 활성화: source $VENV_DIR/bin/activate"
    echo "   서버 실행:       ./run.sh"
    echo "   다른 포트 실행:  ./run.sh --port 9000"
    echo "================================================"
}

main
