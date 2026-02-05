"""GitLab Webhook 처리."""

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from slack_sdk import WebClient

from gitlab_slack.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Slack 클라이언트
slack_client = WebClient(token=settings.slack_bot_token)

# Webhook Secret 미설정 경고
if not settings.gitlab_webhook_secret:
    logger.warning(
        "⚠️  GITLAB_WEBHOOK_SECRET이 설정되지 않았습니다. "
        "프로덕션 환경에서는 반드시 설정하세요!"
    )


@router.post("/webhook")
async def handle_gitlab_webhook(
    request: Request,
    x_gitlab_event: str = Header(None, alias="X-Gitlab-Event"),
    x_gitlab_token: str = Header(None, alias="X-Gitlab-Token"),
):
    """
    GitLab Webhook 이벤트 처리.

    지원 이벤트:
    - Issue Hook: 이슈 생성/수정/상태변경
    """
    if not x_gitlab_event:
        raise HTTPException(status_code=400, detail="Missing X-Gitlab-Event header")

    # Webhook Secret 검증
    if settings.gitlab_webhook_secret:
        if x_gitlab_token != settings.gitlab_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await request.json()

    if x_gitlab_event == "Issue Hook":
        await handle_issue_event(payload)
    else:
        # 지원하지 않는 이벤트는 무시
        pass

    return {"status": "ok"}


async def handle_issue_event(payload: dict):
    """이슈 이벤트 처리."""
    object_attributes = payload.get("object_attributes", {})
    action = object_attributes.get("action")

    issue_iid = object_attributes.get("iid")
    issue_title = object_attributes.get("title")
    issue_url = object_attributes.get("url")
    issue_state = object_attributes.get("state")
    issue_description = object_attributes.get("description", "")

    user = payload.get("user", {})
    user_name = user.get("name", "Unknown")

    # 액션에 따른 메시지 생성
    if action == "open":
        emoji = "🆕"
        action_text = "새 이슈가 생성되었습니다"
    elif action == "close":
        emoji = "✅"
        action_text = "이슈가 종료되었습니다"
    elif action == "reopen":
        emoji = "🔄"
        action_text = "이슈가 다시 열렸습니다"
    elif action == "update":
        emoji = "📝"
        action_text = "이슈가 수정되었습니다"
    else:
        # 기타 액션은 무시
        return

    # 설명 미리보기 (최대 200자)
    description_preview = ""
    if issue_description:
        description_preview = issue_description[:200]
        if len(issue_description) > 200:
            description_preview += "..."

    # Slack 메시지 전송
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
                    "text": f"*이슈:*\n<{issue_url}|#{issue_iid} {issue_title}>",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*상태:*\n`{issue_state}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*담당자:*\n{user_name}",
                },
            ],
        },
    ]

    # 설명이 있으면 추가
    if description_preview:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*설명:*\n{description_preview}",
            },
        })

    # 버튼 추가
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "GitLab에서 보기"},
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
