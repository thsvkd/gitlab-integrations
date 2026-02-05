"""
Slack Modal definitions and submission handlers module.

This module defines the Slack Block Kit modal for issue creation
and handles modal submission events.

Modals:
    build_issue_create_modal: Function to build modal with dynamic labels from GitLab.
"""

import logging
from typing import Any

from slack_bolt import Ack, App
from slack_sdk import WebClient

from gitlab_integrations.config import settings
from gitlab_integrations.gitlab.api import create_issue

# Type alias for Slack Block Kit view/modal structure
SlackModal = dict[str, Any]
SlackBlocks = list[dict[str, Any]]


def build_issue_create_modal(labels: list[dict[str, str]]) -> SlackModal:
    """
    Build issue creation modal with dynamic label options from GitLab.

    Args:
        labels: List of label dictionaries from GitLab with 'name' and 'color' keys.

    Returns:
        SlackModal: Slack Block Kit modal definition.
    """
    # Build label options for the dropdown
    label_options = [
        {
            "text": {"type": "plain_text", "text": label["name"]},
            "value": label["name"],
        }
        for label in labels
    ]

    blocks: SlackBlocks = [
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
    ]

    # Add label selection only if labels exist
    if label_options:
        blocks.append({
            "type": "input",
            "block_id": "labels_block",
            "element": {
                "type": "multi_static_select",
                "action_id": "labels_select",
                "placeholder": {"type": "plain_text", "text": "Select labels"},
                "options": label_options,
            },
            "label": {"type": "plain_text", "text": "Labels"},
            "optional": True,
        })

    return {
        "type": "modal",
        "callback_id": "issue_create_modal",
        "title": {"type": "plain_text", "text": "New Issue"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
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
            - labels_block/labels_select: Labels (optional, multi-select)
            - description_block/description_input: Description (optional)

        Note:
            On success, posts a rich message to the configured Slack channel.
            On failure, posts a simple error message.
        """
        ack()

        # Extract input values from modal
        values: dict[str, Any] = view["state"]["values"]
        title: str = values["title_block"]["title_input"]["value"]
        description: str = values["description_block"]["description_input"].get("value", "") or ""

        # Extract selected labels (multi-select returns list of selected options)
        selected_labels: list[str] = []
        if "labels_block" in values and values["labels_block"]["labels_select"].get(
            "selected_options"
        ):
            selected_labels = [
                option["value"]
                for option in values["labels_block"]["labels_select"]["selected_options"]
            ]

        user_id: str = body["user"]["id"]
        user_name: str = body["user"].get("name", "Unknown")

        # Append Slack user info to description
        full_description: str = f"{description}\n\n---\n_Created from Slack by @{user_name}_"

        try:
            # Create GitLab issue
            issue = create_issue(
                title=title,
                description=full_description,
                labels=selected_labels,
            )

            # Build success message blocks
            blocks: SlackBlocks = _build_issue_created_blocks(
                issue_title=issue.title,
                issue_iid=issue.iid,
                labels=selected_labels,
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
    labels: list[str],
    issue_url: str,
) -> SlackBlocks:
    """
    Build Slack Block Kit blocks for issue creation success message.

    Args:
        issue_title: Title of the created issue.
        issue_iid: Issue number within the project.
        labels: List of label names applied to the issue.
        issue_url: Full URL to the issue in GitLab.

    Returns:
        SlackBlocks: List of Slack Block Kit blocks for the message.
    """
    labels_text = ", ".join(labels) if labels else "None"

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
                    "text": f"*Labels:*\n{labels_text}",
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
