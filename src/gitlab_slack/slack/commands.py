"""Slack Slash command handlers."""

from slack_bolt import App

from gitlab_slack.gitlab.api import get_issue_by_iid
from gitlab_slack.slack.modals import ISSUE_CREATE_MODAL


def register_commands(app: App):
    """Register Slack commands."""

    @app.command("/issue")
    def handle_issue_command(ack, command, client, logger):
        """
        Handle /issue command.

        Usage:
        - /issue : Open issue creation modal
        - /issue status <number> : Check issue status
        """
        ack()

        text = command.get("text", "").strip()
        trigger_id = command["trigger_id"]
        channel_id = command["channel_id"]
        user_id = command["user_id"]

        # Handle /issue status <number>
        if text.startswith("status"):
            parts = text.split()
            if len(parts) >= 2:
                issue_iid = parts[1].lstrip("#")
                try:
                    issue = get_issue_by_iid(int(issue_iid))
                    if issue:
                        state_emoji = "✅" if issue.state == "closed" else "🔵"
                        client.chat_postEphemeral(
                            channel=channel_id,
                            user=user_id,
                            text=f"{state_emoji} *Issue #{issue.iid}*: {issue.title}\n"
                                 f"• Status: `{issue.state}`\n"
                                 f"• Labels: {', '.join(issue.labels) or 'None'}\n"
                                 f"• Link: {issue.web_url}",
                        )
                    else:
                        client.chat_postEphemeral(
                            channel=channel_id,
                            user=user_id,
                            text=f"❌ Issue #{issue_iid} not found.",
                        )
                except Exception as e:
                    logger.error(f"Failed to fetch issue: {e}")
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text="❌ An error occurred while fetching the issue. Please contact the administrator.",
                    )
            else:
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text="Usage: `/issue status <issue_number>`",
                )
            return

        # /issue (Open issue creation modal)
        try:
            client.views_open(trigger_id=trigger_id, view=ISSUE_CREATE_MODAL)
        except Exception as e:
            logger.error(f"Failed to open modal: {e}")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ Failed to open issue creation modal. Please contact the administrator.",
            )
