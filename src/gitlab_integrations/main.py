"""
FastAPI main application module.

This module initializes and configures the FastAPI application
for the GitLab-Slack integration service.

Endpoints:
    GET  /health           - Health check endpoint
    POST /gitlab/webhook   - GitLab webhook receiver
    POST /slack/events     - Slack events endpoint
    POST /slack/commands   - Slack slash commands endpoint
    POST /slack/interactions - Slack modal interactions endpoint

Usage:
    Run directly: python -m gitlab_integrations.main
    Or use the CLI: gitlab-slack --port 8000
"""

import argparse
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, Response
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

from gitlab_integrations.config import settings
from gitlab_integrations.gitlab.webhooks import router as gitlab_router
from gitlab_integrations.slack.commands import register_commands
from gitlab_integrations.slack.modals import register_modals

# Initialize Slack Bolt app with credentials from settings
slack_app: App = App(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)

# Register Slack command and modal handlers
register_commands(slack_app)
register_modals(slack_app)

# Create Slack request handler for FastAPI integration
slack_handler: SlackRequestHandler = SlackRequestHandler(slack_app)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle events.

    This context manager handles startup and shutdown events
    for the FastAPI application.

    Args:
        app: FastAPI application instance.

    Yields:
        None during application runtime.

    Startup:
        - Logs service start message
        - Warns if GITLAB_WEBHOOK_SECRET is not configured

    Shutdown:
        - Logs service stop message
    """
    # Startup
    print("GitLab-Slack Integration service started")

    # Security configuration check
    if not settings.gitlab_webhook_secret:
        print("Warning: GITLAB_WEBHOOK_SECRET is not configured!")
        print("   Please set the Webhook Secret for production environments.")

    yield

    # Shutdown
    print("Service stopped")


# Initialize FastAPI application
app: FastAPI = FastAPI(
    title="GitLab-Slack Integration",
    description="Issue integration service between GitLab and Slack",
    version="0.1.0",
    lifespan=lifespan,
)

# Register GitLab webhook router
app.include_router(gitlab_router, prefix="/gitlab", tags=["gitlab"])


@app.post("/slack/events")
async def slack_events(request: Request) -> Response:
    """
    Handle Slack events.

    This endpoint receives event callbacks from Slack,
    including message events, app mentions, etc.

    Args:
        request: FastAPI request containing Slack event payload.

    Returns:
        Response: Slack handler response.

    Note:
        This endpoint is also used for Slack URL verification
        during app setup (challenge/response).
    """
    return await slack_handler.handle(request)


@app.post("/slack/commands")
async def slack_commands(request: Request) -> Response:
    """
    Handle Slack slash commands.

    This endpoint receives slash command invocations from Slack
    (e.g., /issue, /issue status 123).

    Args:
        request: FastAPI request containing command payload.

    Returns:
        Response: Slack handler response.

    Supported Commands:
        /issue - Opens issue creation modal
        /issue status <number> - Shows issue status
    """
    return await slack_handler.handle(request)


@app.post("/slack/interactions")
async def slack_interactions(request: Request) -> Response:
    """
    Handle Slack interactive components.

    This endpoint receives interactions from Slack UI components
    such as modal submissions, button clicks, etc.

    Args:
        request: FastAPI request containing interaction payload.

    Returns:
        Response: Slack handler response.

    Supported Interactions:
        - issue_create_modal: Issue creation form submission
        - Button clicks from issue notifications
    """
    return await slack_handler.handle(request)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns basic service health information for monitoring
    and load balancer health checks.

    Returns:
        dict[str, str]: Health status response containing:
            - status: "healthy" if service is running
            - service: Service identifier
    """
    return {"status": "healthy", "service": "gitlab-slack-integration"}


def main() -> None:
    """
    Run the server with uvicorn.

    Parses command line arguments and starts the uvicorn server.
    This function is the entry point for the 'gitlab-slack' CLI command.

    Command Line Arguments:
        -p, --port: Server port (default: from settings or 8000)
        -H, --host: Server host (default: from settings or 0.0.0.0)
        --no-reload: Disable auto-reload for production

    Example:
        gitlab-slack --port 8080 --no-reload
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="GitLab-Slack Integration Server"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=settings.port,
        help=f"Server port (default: {settings.port})",
    )
    parser.add_argument(
        "-H", "--host",
        type=str,
        default=settings.host,
        help=f"Server host (default: {settings.host})",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload",
    )
    args: argparse.Namespace = parser.parse_args()

    uvicorn.run(
        "gitlab_integrations.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
