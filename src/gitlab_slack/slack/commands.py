"""Slack Slash 커맨드 처리."""

from slack_bolt import App

from gitlab_slack.gitlab.api import get_issue_by_iid
from gitlab_slack.slack.modals import ISSUE_CREATE_MODAL


def register_commands(app: App):
    """Slack 커맨드 등록."""

    @app.command("/issue")
    def handle_issue_command(ack, command, client, logger):
        """
        /issue 커맨드 처리.

        사용법:
        - /issue : 이슈 생성 모달 열기
        - /issue status <번호> : 이슈 상태 조회
        """
        ack()

        text = command.get("text", "").strip()
        trigger_id = command["trigger_id"]
        channel_id = command["channel_id"]
        user_id = command["user_id"]

        # /issue status <번호> 처리
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
                            text=f"{state_emoji} *이슈 #{issue.iid}*: {issue.title}\n"
                                 f"• 상태: `{issue.state}`\n"
                                 f"• 라벨: {', '.join(issue.labels) or '없음'}\n"
                                 f"• 링크: {issue.web_url}",
                        )
                    else:
                        client.chat_postEphemeral(
                            channel=channel_id,
                            user=user_id,
                            text=f"❌ 이슈 #{issue_iid}를 찾을 수 없습니다.",
                        )
                except Exception as e:
                    logger.error(f"이슈 조회 실패: {e}")
                    client.chat_postEphemeral(
                        channel=channel_id,
                        user=user_id,
                        text=f"❌ 이슈 조회 중 오류가 발생했습니다: {e}",
                    )
            else:
                client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text="사용법: `/issue status <이슈번호>`",
                )
            return

        # /issue (이슈 생성 모달 열기)
        try:
            client.views_open(trigger_id=trigger_id, view=ISSUE_CREATE_MODAL)
        except Exception as e:
            logger.error(f"모달 열기 실패: {e}")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ 이슈 생성 모달을 열 수 없습니다: {e}",
            )
