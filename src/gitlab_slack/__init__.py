"""
GitLab-Slack Integration Service.

This package provides a FastAPI-based service for integrating
GitLab issues with Slack, allowing:
- Creating GitLab issues from Slack using /issue command
- Receiving notifications in Slack when GitLab issues change
- Checking issue status from Slack using /issue status <number>

Modules:
    config: Application configuration and settings.
    main: FastAPI application and entry point.
    gitlab: GitLab API client and webhook handlers.
    slack: Slack command handlers and modal definitions.
"""

__version__: str = "0.1.0"
