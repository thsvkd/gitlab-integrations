"""
GitLab Webhook handlers module.

This module handles incoming webhooks from GitLab and posts
notifications to Slack for issue-related events.

Supported Events:
    - Issue Hook: Triggered when issues are created, updated, closed, or reopened.

Security:
    Webhook secret validation is enforced when GITLAB_WEBHOOK_SECRET is configured.
"""

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from slack_sdk import WebClient
from slack_sdk.web import SlackResponse

from gitlab_integrations.config import settings

logger: logging.Logger = logging.getLogger(__name__)

router: APIRouter = APIRouter()

# Slack client for posting notifications
slack_client: WebClient = WebClient(token=settings.slack_bot_token)

# Warning if Webhook Secret is not configured
if not settings.gitlab_webhook_secret:
    logger.warning(
        "GITLAB_WEBHOOK_SECRET is not configured. "
        "Please set it for production environments!"
    )


# Type alias for GitLab webhook payload
GitLabWebhookPayload = dict[str, Any]


@router.post("/webhook")
async def handle_gitlab_webhook(
    request: Request,
    x_gitlab_event: str | None = Header(None, alias="X-Gitlab-Event"),
    x_gitlab_token: str | None = Header(None, alias="X-Gitlab-Token"),
) -> dict[str, str]:
    """
    Handle incoming GitLab webhook events.

    This endpoint receives webhook events from GitLab and routes them
    to appropriate handlers based on the event type.

    Args:
        request: FastAPI request object containing the webhook payload.
        x_gitlab_event: GitLab event type header (e.g., "Issue Hook").
        x_gitlab_token: GitLab webhook secret token for authentication.

    Returns:
        dict[str, str]: Response with status "ok" on success.

    Raises:
        HTTPException: 400 if X-Gitlab-Event header is missing.
        HTTPException: 401 if webhook token is invalid.

    Supported Events:
        - Issue Hook: Issue create/update/close/reopen events.

    Note:
        Events not listed above are silently ignored with status "ok".
    """
    if not x_gitlab_event:
        raise HTTPException(status_code=400, detail="Missing X-Gitlab-Event header")

    # Webhook Secret verification
    if settings.gitlab_webhook_secret:
        if x_gitlab_token != settings.gitlab_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload: GitLabWebhookPayload = await request.json()

    if x_gitlab_event == "Issue Hook":
        await handle_issue_event(payload)
    # Other events are silently ignored

    return {"status": "ok"}


async def handle_issue_event(payload: GitLabWebhookPayload) -> None:
    """
    Handle GitLab issue events and post notifications to Slack.

    Processes issue events (open, close, reopen, update) and sends
    formatted notifications to the configured Slack channel.

    Args:
        payload: GitLab webhook payload containing issue data.
            Expected structure:
            {
                "object_attributes": {
                    "action": str,  # "open", "close", "reopen", "update"
                    "iid": int,
                    "title": str,
                    "url": str,
                    "state": str,
                    "description": str
                },
                "user": {"name": str}
            }

    Returns:
        None. Sends Slack message as side effect.

    Note:
        Unknown actions (other than open/close/reopen/update) are ignored.
        Long descriptions are truncated to 200 characters.
    """
    object_attributes: dict[str, Any] = payload.get("object_attributes", {})
    action: str | None = object_attributes.get("action")

    issue_iid: int | None = object_attributes.get("iid")
    issue_title: str | None = object_attributes.get("title")
    issue_url: str | None = object_attributes.get("url")
    issue_state: str | None = object_attributes.get("state")
    issue_description: str = object_attributes.get("description", "") or ""

    user: dict[str, Any] = payload.get("user", {})
    user_name: str = user.get("name", "Unknown")

    # Map action to emoji and message text
    action_map: dict[str, tuple[str, str]] = {
        "open": ("🆕", "New issue created"),
        "close": ("✅", "Issue closed"),
        "reopen": ("🔄", "Issue reopened"),
        "update": ("📝", "Issue updated"),
    }

    if action not in action_map:
        # Ignore unknown actions
        return

    emoji, action_text = action_map[action]

    # Truncate long descriptions (max 200 characters)
    description_preview: str = _truncate_text(issue_description, max_length=200)

    # Build Slack message blocks
    blocks: list[dict[str, Any]] = _build_issue_notification_blocks(
        emoji=emoji,
        action_text=action_text,
        issue_iid=issue_iid,
        issue_title=issue_title,
        issue_url=issue_url,
        issue_state=issue_state,
        user_name=user_name,
        description_preview=description_preview,
    )

    # Send Slack notification
    slack_client.chat_postMessage(
        channel=settings.slack_channel_id,
        text=f"{emoji} {action_text}: #{issue_iid} {issue_title}",
        blocks=blocks,
    )


def _truncate_text(text: str, max_length: int = 200) -> str:
    """
    Truncate text to specified length with ellipsis.

    Args:
        text: Text to truncate.
        max_length: Maximum length before truncation.

    Returns:
        str: Truncated text with "..." suffix if exceeded max_length,
            or original text if within limit.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _build_issue_notification_blocks(
    emoji: str,
    action_text: str,
    issue_iid: int | None,
    issue_title: str | None,
    issue_url: str | None,
    issue_state: str | None,
    user_name: str,
    description_preview: str,
) -> list[dict[str, Any]]:
    """
    Build Slack Block Kit blocks for issue notification.

    Args:
        emoji: Emoji for the notification header.
        action_text: Action description text.
        issue_iid: Issue number within the project.
        issue_title: Issue title.
        issue_url: Full URL to the issue in GitLab.
        issue_state: Current issue state (opened/closed).
        user_name: Name of the user who triggered the action.
        description_preview: Truncated issue description.

    Returns:
        list[dict[str, Any]]: Slack Block Kit blocks for the message.
    """
    blocks: list[dict[str, Any]] = [
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

    # Add description block if available
    if description_preview:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n{description_preview}",
            },
        })

    # Add "View in GitLab" button
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

    return blocks
