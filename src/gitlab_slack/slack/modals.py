"""Slack Modal definitions and handlers."""

from slack_bolt import App

from gitlab_slack.config import settings
from gitlab_slack.gitlab.api import create_issue

# Issue creation modal definition
ISSUE_CREATE_MODAL = {
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
                        "text": {"type": "plain_text", "text": "🐛 Bug"},
                        "value": "bug",
                    },
                    {
                        "text": {"type": "plain_text", "text": "✨ Feature Request"},
                        "value": "feature",
                    },
                    {
                        "text": {"type": "plain_text", "text": "📝 Documentation"},
                        "value": "documentation",
                    },
                    {
                        "text": {"type": "plain_text", "text": "❓ Question"},
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
                        "text": {"type": "plain_text", "text": "🔴 Critical"},
                        "value": "critical",
                    },
                    {
                        "text": {"type": "plain_text", "text": "🟠 High"},
                        "value": "high",
                    },
                    {
                        "text": {"type": "plain_text", "text": "🟡 Medium"},
                        "value": "medium",
                    },
                    {
                        "text": {"type": "plain_text", "text": "🟢 Low"},
                        "value": "low",
                    },
                ],
                "initial_option": {
                    "text": {"type": "plain_text", "text": "🟡 Medium"},
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


def register_modals(app: App):
    """Register modal submission handlers."""

    @app.view("issue_create_modal")
    def handle_issue_create_submission(ack, body, client, view, logger):
        """Handle issue creation modal submission."""
        ack()

        # Extract input values
        values = view["state"]["values"]
        title = values["title_block"]["title_input"]["value"]
        issue_type = values["type_block"]["type_select"]["selected_option"]["value"]
        priority = values["priority_block"]["priority_select"]["selected_option"]["value"]
        description = values["description_block"]["description_input"].get("value", "")

        user_id = body["user"]["id"]
        user_name = body["user"].get("name", "Unknown")

        # Label mapping
        labels = [f"type::{issue_type}", f"priority::{priority}"]

        # Add Slack user info to description
        full_description = f"{description}\n\n---\n_Created from Slack by @{user_name}_"

        try:
            # Create GitLab issue
            issue = create_issue(
                title=title,
                description=full_description,
                labels=labels,
            )

            # Send success message
            client.chat_postMessage(
                channel=settings.slack_channel_id,
                text="✅ New issue has been created!",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "✅ *New issue has been created!*",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Title:*\n{issue.title}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Issue Number:*\n#{issue.iid}",
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
                                "url": issue.web_url,
                                "action_id": "view_gitlab_issue",
                            },
                        ],
                    },
                ],
            )

            logger.info(f"Issue created successfully: #{issue.iid} - {title}")

        except Exception as e:
            logger.error(f"Failed to create issue: {e}")
            client.chat_postMessage(
                channel=settings.slack_channel_id,
                text="❌ Failed to create issue. Please contact the administrator.",
            )
