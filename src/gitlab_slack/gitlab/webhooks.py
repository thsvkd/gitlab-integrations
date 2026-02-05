"""GitLab Webhook handlers."""

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from slack_sdk import WebClient

from gitlab_slack.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Slack client
slack_client = WebClient(token=settings.slack_bot_token)

# Warning if Webhook Secret is not configured
if not settings.gitlab_webhook_secret:
    logger.warning(
        "⚠️  GITLAB_WEBHOOK_SECRET is not configured. "
        "Please set it for production environments!"
    )


@router.post("/webhook")
async def handle_gitlab_webhook(
    request: Request,
    x_gitlab_event: str = Header(None, alias="X-Gitlab-Event"),
    x_gitlab_token: str = Header(None, alias="X-Gitlab-Token"),
):
    """
    Handle GitLab Webhook events.

    Supported events:
    - Issue Hook: Issue create/update/state change
    """
    if not x_gitlab_event:
        raise HTTPException(status_code=400, detail="Missing X-Gitlab-Event header")

    # Webhook Secret verification
    if settings.gitlab_webhook_secret:
        if x_gitlab_token != settings.gitlab_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await request.json()

    if x_gitlab_event == "Issue Hook":
        await handle_issue_event(payload)
    else:
        # Ignore unsupported events
        pass

    return {"status": "ok"}


async def handle_issue_event(payload: dict):
    """Handle issue events."""
    object_attributes = payload.get("object_attributes", {})
    action = object_attributes.get("action")

    issue_iid = object_attributes.get("iid")
    issue_title = object_attributes.get("title")
    issue_url = object_attributes.get("url")
    issue_state = object_attributes.get("state")
    issue_description = object_attributes.get("description", "")

    user = payload.get("user", {})
    user_name = user.get("name", "Unknown")

    # Generate message based on action
    if action == "open":
        emoji = "🆕"
        action_text = "New issue created"
    elif action == "close":
        emoji = "✅"
        action_text = "Issue closed"
    elif action == "reopen":
        emoji = "🔄"
        action_text = "Issue reopened"
    elif action == "update":
        emoji = "📝"
        action_text = "Issue updated"
    else:
        # Ignore other actions
        return

    # Description preview (max 200 characters)
    description_preview = ""
    if issue_description:
        description_preview = issue_description[:200]
        if len(issue_description) > 200:
            description_preview += "..."

    # Send Slack message
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{action_text}*",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Issue:*\n<{issue_url}|#{issue_iid} {issue_title}>",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Status:*\n`{issue_state}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Author:*\n{user_name}",
                },
            ],
        },
    ]

    # Add description if available
    if description_preview:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n{description_preview}",
            },
        })

    # Add button
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View in GitLab"},
                "url": issue_url,
                "action_id": "view_issue_from_webhook",
            },
        ],
    })

    slack_client.chat_postMessage(
        channel=settings.slack_channel_id,
        text=f"{emoji} {action_text}: #{issue_iid} {issue_title}",
        blocks=blocks,
    )
