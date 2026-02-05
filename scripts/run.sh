#!/bin/bash
# GitLab-Slack Integration 실행 스크립트

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

VENV_DIR=".venv"

# 가상환경 확인
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 가상환경이 없습니다. 먼저 setup.sh를 실행해주세요."
    echo "   ./scripts/setup.sh"
    exit 1
fi

# 가상환경 활성화
source "$VENV_DIR/bin/activate"

# .env 파일 확인 및 로드
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다. 환경 변수를 설정해주세요."
    exit 1
fi

# .env에서 HOST, PORT 읽기
source <(grep -E '^(HOST|PORT)=' .env | sed 's/^/export /')
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

echo "🚀 GitLab-Slack Integration 서버 시작"
echo "================================================"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "================================================"

# 인자가 없으면 .env의 HOST, PORT 사용
if [ $# -eq 0 ]; then
    exec python -m gitlab_slack.main --host "$HOST" --port "$PORT"
else
    # 인자가 있으면 그대로 전달
    exec python -m gitlab_slack.main "$@"
fi
