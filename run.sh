#!/bin/bash
# GitLab-Slack Integration 실행 스크립트

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"

# 가상환경 확인
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 가상환경이 없습니다. 먼저 setup.sh를 실행해주세요."
    echo "   ./setup.sh"
    exit 1
fi

# 가상환경 활성화
source "$VENV_DIR/bin/activate"

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다. 환경 변수를 설정해주세요."
    exit 1
fi

echo "🚀 GitLab-Slack Integration 서버 시작"
echo "================================================"

# 모든 인자를 그대로 전달
exec gitlab-slack "$@"
