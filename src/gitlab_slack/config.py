"""Configuration module."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # GitLab settings
    gitlab_url: str
    gitlab_token: str
    gitlab_project_id: int
    gitlab_webhook_secret: str | None = None

    # Slack settings
    slack_bot_token: str
    slack_signing_secret: str
    slack_channel_id: str

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
