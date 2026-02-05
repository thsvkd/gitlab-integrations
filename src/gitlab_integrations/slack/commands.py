"""
Slack Slash command handlers module.

This module defines handlers for Slack slash commands,
primarily the /issue command for interacting with GitLab issues.

Commands:
    /issue: Opens issue creation modal with dynamic labels from GitLab.
    /issue status <number>: Shows status of a specific issue.
"""

import logging
from typing import Any

from slack_bolt import Ack, App
from slack_sdk import WebClient

from gitlab_integrations.gitlab.api import get_issue_by_iid, list_labels
from gitlab_integrations.slack.modals import build_issue_create_modal


def register_commands(app: App) -> None:
    """
    Register Slack slash command handlers with the app.

    This function registers all slash command handlers supported by
    the integration service.

    Args:
        app: Slack Bolt app instance to register commands with.

    Registered Commands:
        /issue: Issue management command (see handle_issue_command).
    """

    @app.command("/issue")
    def handle_issue_command(
        ack: Ack,
        command: dict[str, Any],
        client: WebClient,
        logger: logging.Logger,
    ) -> None:
        """
        Handle /issue slash command.

        This command supports two modes:
        1. /issue - Opens a modal for creating a new GitLab issue.
        2. /issue status <number> - Shows the status of an existing issue.

        Args:
            ack: Acknowledge function to respond to Slack within 3 seconds.
            command: Command payload containing:
                - text: Command arguments (e.g., "status 123")
                - trigger_id: ID for opening modals
                - channel_id: Channel where command was invoked
                - user_id: User who invoked the command
            client: Slack WebClient for API calls.
            logger: Logger instance for error logging.

        Usage:
            /issue              - Opens issue creation modal
            /issue status 123   - Shows status of issue #123
            /issue status #123  - Also works with # prefix

        Note:
            Error messages are sent as ephemeral messages visible only
            to the invoking user.
        """
        ack()

        text: str = command.get("text", "").strip()
        trigger_id: str = command["trigger_id"]
        channel_id: str = command["channel_id"]
        user_id: str = command["user_id"]

        # Handle /issue status <number>
        if text.startswith("status"):
            _handle_status_subcommand(
                text=text,
                channel_id=channel_id,
                user_id=user_id,
                client=client,
                logger=logger,
            )
            return

        # /issue (Open issue creation modal)
        _open_issue_modal(
            trigger_id=trigger_id,
            channel_id=channel_id,
            user_id=user_id,
            client=client,
            logger=logger,
        )


def _handle_status_subcommand(
    text: str,
    channel_id: str,
    user_id: str,
    client: WebClient,
    logger: logging.Logger,
) -> None:
    """
    Handle /issue status <number> subcommand.

    Retrieves and displays the status of a GitLab issue.

    Args:
        text: Full command text (e.g., "status 123").
        channel_id: Slack channel ID for ephemeral response.
        user_id: Slack user ID for ephemeral response.
        client: Slack WebClient for API calls.
        logger: Logger for error logging.

    Note:
        Sends ephemeral message with issue status or error message.
    """
    parts: list[str] = text.split()

    if len(parts) < 2:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="Usage: `/issue status <issue_number>`",
        )
        return

    # Parse issue number (remove # prefix if present)
    issue_iid_str: str = parts[1].lstrip("#")

    try:
        issue_iid: int = int(issue_iid_str)
        issue = get_issue_by_iid(issue_iid)

        if issue:
            state_emoji: str = "✅" if issue.state == "closed" else "🔵"
            labels_text: str = ", ".join(issue.labels) if issue.labels else "None"

            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=(
                    f"{state_emoji} *Issue #{issue.iid}*: {issue.title}\n"
                    f"• Status: `{issue.state}`\n"
                    f"• Labels: {labels_text}\n"
                    f"• Link: {issue.web_url}"
                ),
            )
        else:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ Issue #{issue_iid} not found.",
            )

    except ValueError:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"❌ Invalid issue number: {issue_iid_str}",
        )
    except Exception as e:
        logger.error(f"Failed to fetch issue: {e}")
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="❌ An error occurred while fetching the issue. Please contact the administrator.",
        )


def _open_issue_modal(
    trigger_id: str,
    channel_id: str,
    user_id: str,
    client: WebClient,
    logger: logging.Logger,
) -> None:
    """
    Open the issue creation modal with dynamic labels from GitLab.

    Args:
        trigger_id: Slack trigger ID for opening the modal.
        channel_id: Channel ID for error messages.
        user_id: User ID for error messages.
        client: Slack WebClient for API calls.
        logger: Logger for error logging.

    Note:
        On failure, sends ephemeral error message to the user.
        Labels are fetched from GitLab at runtime for dynamic dropdown.
    """
    try:
        # Fetch labels from GitLab
        labels = list_labels()

        # Build modal with dynamic labels
        modal = build_issue_create_modal(labels)

        client.views_open(trigger_id=trigger_id, view=modal)
    except Exception as e:
        logger.error(f"Failed to open modal: {e}")
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="❌ Failed to open issue creation modal. Please contact the administrator.",
        )
