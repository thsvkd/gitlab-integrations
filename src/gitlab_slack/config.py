"""
Configuration module for GitLab-Slack Integration.

This module defines the application settings using Pydantic BaseSettings,
which automatically loads values from environment variables or .env file.
"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be configured via environment variables or .env file.
    Environment variable names are case-insensitive.

    Attributes:
        gitlab_url: GitLab server URL (e.g., https://gitlab.example.com)
        gitlab_token: GitLab personal access token with API permissions
        gitlab_project_id: GitLab project ID where issues will be created
        gitlab_webhook_secret: Secret token for validating GitLab webhooks (optional)
        slack_bot_token: Slack Bot OAuth token (xoxb-...)
        slack_signing_secret: Slack app signing secret for request verification
        slack_channel_id: Slack channel ID for posting notifications
        host: Server host address (default: 0.0.0.0)
        port: Server port number (default: 8000)
    """

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

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


# Global settings instance
settings: Settings = Settings()
