"""FastAPI main application."""

import argparse
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler

from gitlab_slack.config import settings
from gitlab_slack.gitlab.webhooks import router as gitlab_router
from gitlab_slack.slack.commands import register_commands
from gitlab_slack.slack.modals import register_modals

# Initialize Slack Bolt app
slack_app = App(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)

# Register commands and modals
register_commands(slack_app)
register_modals(slack_app)

# Slack request handler
slack_handler = SlackRequestHandler(slack_app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    print("🚀 GitLab-Slack Integration service started")

    # Security configuration check
    if not settings.gitlab_webhook_secret:
        print("⚠️  Warning: GITLAB_WEBHOOK_SECRET is not configured!")
        print("   Please set the Webhook Secret for production environments.")

    yield
    print("👋 Service stopped")


# Initialize FastAPI app
app = FastAPI(
    title="GitLab-Slack Integration",
    description="Issue integration service between GitLab and Slack",
    version="0.1.0",
    lifespan=lifespan,
)

# Register GitLab webhook router
app.include_router(gitlab_router, prefix="/gitlab", tags=["gitlab"])


@app.post("/slack/events")
async def slack_events(request: Request):
    """Slack events endpoint."""
    return await slack_handler.handle(request)


@app.post("/slack/commands")
async def slack_commands(request: Request):
    """Slack commands endpoint."""
    return await slack_handler.handle(request)


@app.post("/slack/interactions")
async def slack_interactions(request: Request):
    """Slack interactions endpoint (Modal, etc.)."""
    return await slack_handler.handle(request)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gitlab-slack-integration"}


def main():
    """Run server."""
    parser = argparse.ArgumentParser(description="GitLab-Slack Integration Server")
    parser.add_argument("-p", "--port", type=int, default=settings.port, help=f"Server port (default: {settings.port})")
    parser.add_argument("-H", "--host", type=str, default=settings.host, help=f"Server host (default: {settings.host})")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "gitlab_slack.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
    )


if __name__ == "__main__":
    main()
