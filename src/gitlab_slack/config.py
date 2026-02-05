"""환경 설정 모듈."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정."""

    # GitLab 설정
    gitlab_url: str
    gitlab_token: str
    gitlab_project_id: int
    gitlab_webhook_secret: str | None = None

    # Slack 설정
    slack_bot_token: str
    slack_signing_secret: str
    slack_channel_id: str

    # 서버 설정
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
