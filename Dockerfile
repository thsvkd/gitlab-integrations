FROM python:3.10-slim

WORKDIR /app

# uv 설치
RUN pip install uv

# 의존성 파일 복사 및 설치
COPY pyproject.toml .
RUN uv pip install --system -e .

# 소스 코드 복사
COPY src/ ./src/

# 환경변수
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["python", "-m", "gitlab_slack.main"]
