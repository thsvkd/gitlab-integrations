"""Slack Modal 정의 및 처리."""

from slack_bolt import App

from gitlab_slack.config import settings
from gitlab_slack.gitlab.api import create_issue

# 이슈 생성 모달 정의
ISSUE_CREATE_MODAL = {
    "type": "modal",
    "callback_id": "issue_create_modal",
    "title": {"type": "plain_text", "text": "새 이슈 등록"},
    "submit": {"type": "plain_text", "text": "생성하기"},
    "close": {"type": "plain_text", "text": "취소"},
    "blocks": [
        {
            "type": "input",
            "block_id": "title_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "title_input",
                "placeholder": {"type": "plain_text", "text": "이슈 제목을 입력하세요"},
            },
            "label": {"type": "plain_text", "text": "제목"},
        },
        {
            "type": "input",
            "block_id": "type_block",
            "element": {
                "type": "static_select",
                "action_id": "type_select",
                "placeholder": {"type": "plain_text", "text": "유형 선택"},
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "🐛 버그"},
                        "value": "bug",
                    },
                    {
                        "text": {"type": "plain_text", "text": "✨ 기능 요청"},
                        "value": "feature",
                    },
                    {
                        "text": {"type": "plain_text", "text": "📝 문서"},
                        "value": "documentation",
                    },
                    {
                        "text": {"type": "plain_text", "text": "❓ 질문"},
                        "value": "question",
                    },
                ],
            },
            "label": {"type": "plain_text", "text": "유형"},
        },
        {
            "type": "input",
            "block_id": "priority_block",
            "element": {
                "type": "static_select",
                "action_id": "priority_select",
                "placeholder": {"type": "plain_text", "text": "우선순위 선택"},
                "options": [
                    {
                        "text": {"type": "plain_text", "text": "🔴 긴급"},
                        "value": "critical",
                    },
                    {
                        "text": {"type": "plain_text", "text": "🟠 높음"},
                        "value": "high",
                    },
                    {
                        "text": {"type": "plain_text", "text": "🟡 보통"},
                        "value": "medium",
                    },
                    {
                        "text": {"type": "plain_text", "text": "🟢 낮음"},
                        "value": "low",
                    },
                ],
                "initial_option": {
                    "text": {"type": "plain_text", "text": "🟡 보통"},
                    "value": "medium",
                },
            },
            "label": {"type": "plain_text", "text": "우선순위"},
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
                    "text": "이슈에 대한 상세 설명을 입력하세요",
                },
            },
            "label": {"type": "plain_text", "text": "설명"},
            "optional": True,
        },
    ],
}


def register_modals(app: App):
    """Modal 제출 핸들러 등록."""

    @app.view("issue_create_modal")
    def handle_issue_create_submission(ack, body, client, view, logger):
        """이슈 생성 모달 제출 처리."""
        ack()

        # 입력값 추출
        values = view["state"]["values"]
        title = values["title_block"]["title_input"]["value"]
        issue_type = values["type_block"]["type_select"]["selected_option"]["value"]
        priority = values["priority_block"]["priority_select"]["selected_option"]["value"]
        description = values["description_block"]["description_input"].get("value", "")

        user_id = body["user"]["id"]
        user_name = body["user"].get("name", "Unknown")

        # 라벨 매핑
        labels = [f"type::{issue_type}", f"priority::{priority}"]

        # 설명에 Slack 사용자 정보 추가
        full_description = f"{description}\n\n---\n_Slack에서 생성됨 by @{user_name}_"

        try:
            # GitLab 이슈 생성
            issue = create_issue(
                title=title,
                description=full_description,
                labels=labels,
            )

            # 성공 메시지 전송
            client.chat_postMessage(
                channel=settings.slack_channel_id,
                text=f"✅ 새 이슈가 생성되었습니다!",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ *새 이슈가 생성되었습니다!*",
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*제목:*\n{issue.title}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*이슈 번호:*\n#{issue.iid}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*유형:*\n{issue_type}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*우선순위:*\n{priority}",
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
                                    "text": "GitLab에서 보기",
                                },
                                "url": issue.web_url,
                                "action_id": "view_gitlab_issue",
                            },
                        ],
                    },
                ],
            )

            logger.info(f"이슈 생성 성공: #{issue.iid} - {title}")

        except Exception as e:
            logger.error(f"이슈 생성 실패: {e}")
            client.chat_postMessage(
                channel=settings.slack_channel_id,
                text="❌ 이슈 생성에 실패했습니다. 관리자에게 문의하세요.",
            )
