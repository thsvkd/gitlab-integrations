"""
Slack Modal definitions and submission handlers module.

This module defines the Slack Block Kit modal for issue creation
and handles modal submission events.

Modals:
    ISSUE_CREATE_MODAL: Modal for creating new GitLab issues with
        title, type, priority, and description fields.
"""

import logging
from typing import Any

from slack_bolt import Ack, App
from slack_sdk import WebClient

from gitlab_slack.config import settings
from gitlab_slack.gitlab.api import create_issue

# Type alias for Slack Block Kit view/modal structure
SlackModal = dict[str, Any]
SlackBlocks = list[dict[str, Any]]


# Issue creation modal definition
ISSUE_CREATE_MODAL: SlackModal = {
    "type": "modal",
    "callback_id": "issue_create_modal",
    "title": {"type": "plain_text", "text": "New Issue"},
    "submit": {"type": "plain_text", "text": "Create"},
    "close": {"type": "plain_text", "text": "Cancel"},
    "blocks": [
        {
            "type": "input",
            "block_id": "title_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "title_input",
                "placeholder": {"type": "plain_text", "text": "Enter issue title"},
            },
            "label": {"type": "plain_text", "text": "Title"},
        },
        {
            "type": "input",
            "block_id": "type_block",
            "element": {
                "type": "static_select",
                "action_id": "type_select",
                "placeholder": {"type": "plain_text", "text": "Select type"},
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "Bug"},
                        "value": "bug",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Feature Request"},
                        "value": "feature",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Documentation"},
                        "value": "documentation",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Question"},
                        "value": "question",
                    },
                ],
            },
            "label": {"type": "plain_text", "text": "Type"},
        },
        {
            "type": "input",
            "block_id": "priority_block",
            "element": {
                "type": "static_select",
                "action_id": "priority_select",
                "placeholder": {"type": "plain_text", "text": "Select priority"},
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "Critical"},
                        "value": "critical",
                    },
                    {
                        "text": {"type": "plain_text", "text": "High"},
                        "value": "high",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Medium"},
                        "value": "medium",
                    },
                    {
                        "text": {"type": "plain_text", "text": "Low"},
                        "value": "low",
                    },
                ],
                "initial_option": {
                    "text": {"type": "plain_text", "text": "Medium"},
                    "value": "medium",
                },
            },
            "label": {"type": "plain_text", "text": "Priority"},
        },
        {
            "type": "input",
            "block_id": "description_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "description_input",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter detailed description",
                },
            },
            "label": {"type": "plain_text", "text": "Description"},
            "optional": True,
        },
    ],
}


def register_modals(app: App) -> None:
    """
    Register modal submission handlers with the Slack app.

    This function registers handlers for all modal submissions
    supported by the integration service.

    Args:
        app: Slack Bolt app instance to register handlers with.

    Registered Handlers:
        issue_create_modal: Handler for issue creation modal submission.
    """

    @app.view("issue_create_modal")
    def handle_issue_create_submission(
        ack: Ack,
        body: dict[str, Any],
        client: WebClient,
        view: dict[str, Any],
        logger: logging.Logger,
    ) -> None:
        """
        Handle issue creation modal submission.

        Extracts form data from the modal, creates a GitLab issue,
        and posts a success/failure message to Slack.

        Args:
            ack: Acknowledge function to respond to Slack within 3 seconds.
            body: Full request body containing user information:
                - user.id: Slack user ID
                - user.name: Slack user display name
            client: Slack WebClient for API calls.
            view: Modal view state containing form values:
                - state.values: Form input values by block_id
            logger: Logger instance for error/info logging.

        Form Fields:
            - title_block/title_input: Issue title (required)
            - type_block/type_select: Issue type (bug/feature/etc.)
            - priority_block/priority_select: Priority level
            - description_block/description_input: Description (optional)

        GitLab Labels:
            Creates labels in format: type::<type>, priority::<priority>

        Note:
            On success, posts a rich message to the configured Slack channel.
            On failure, posts a simple error message.
        """
        ack()

        # Extract input values from modal
        values: dict[str, Any] = view["state"]["values"]
        title: str = values["title_block"]["title_input"]["value"]
        issue_type: str = values["type_block"]["type_select"]["selected_option"]["value"]
        priority: str = values["priority_block"]["priority_select"]["selected_option"]["value"]
        description: str = values["description_block"]["description_input"].get("value", "") or ""

        user_id: str = body["user"]["id"]
        user_name: str = body["user"].get("name", "Unknown")

        # Build GitLab labels from type and priority
        labels: list[str] = [f"type::{issue_type}", f"priority::{priority}"]

        # Append Slack user info to description
        full_description: str = f"{description}\n\n---\n_Created from Slack by @{user_name}_"

        try:
            # Create GitLab issue
            issue = create_issue(
                title=title,
                description=full_description,
                labels=labels,
            )

            # Build success message blocks
            blocks: SlackBlocks = _build_issue_created_blocks(
                issue_title=issue.title,
                issue_iid=issue.iid,
                issue_type=issue_type,
                priority=priority,
                issue_url=issue.web_url,
            )

            # Post success message to channel
            client.chat_postMessage(
                channel=settings.slack_channel_id,
                text="New issue has been created!",
                blocks=blocks,
            )

            logger.info(f"Issue created successfully: #{issue.iid} - {title}")

        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            client.chat_postMessage(
                channel=settings.slack_channel_id,
                text="Failed to create issue. Please contact the administrator.",
            )


def _build_issue_created_blocks(
    issue_title: str,
    issue_iid: int,
    issue_type: str,
    priority: str,
    issue_url: str,
) -> SlackBlocks:
    """
    Build Slack Block Kit blocks for issue creation success message.

    Args:
        issue_title: Title of the created issue.
        issue_iid: Issue number within the project.
        issue_type: Type label (bug/feature/etc.).
        priority: Priority label (critical/high/medium/low).
        issue_url: Full URL to the issue in GitLab.

    Returns:
        SlackBlocks: List of Slack Block Kit blocks for the message.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*New issue has been created!*",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Title:*\n{issue_title}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Issue Number:*\n#{issue_iid}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Type:*\n{issue_type}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Priority:*\n{priority}",
                },
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View in GitLab",
                    },
                    "url": issue_url,
                    "action_id": "view_gitlab_issue",
                },
            ],
        },
    ]
