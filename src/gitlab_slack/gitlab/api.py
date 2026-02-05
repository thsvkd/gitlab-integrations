"""GitLab API 클라이언트."""

import gitlab

from gitlab_slack.config import settings

# GitLab 클라이언트 초기화 (self-signed 인증서 허용)
gl = gitlab.Gitlab(
    settings.gitlab_url,
    private_token=settings.gitlab_token,
    ssl_verify=False,
)


def get_project():
    """GitLab 프로젝트 객체 반환."""
    return gl.projects.get(settings.gitlab_project_id)


def create_issue(title: str, description: str = "", labels: list[str] | None = None):
    """
    GitLab에 새 이슈 생성.

    Args:
        title: 이슈 제목
        description: 이슈 설명
        labels: 라벨 목록

    Returns:
        생성된 이슈 객체
    """
    project = get_project()
    issue = project.issues.create({
        "title": title,
        "description": description,
        "labels": labels or [],
    })
    return issue


def get_issue_by_iid(iid: int):
    """
    이슈 번호(IID)로 이슈 조회.

    Args:
        iid: 프로젝트 내 이슈 번호 (#123 형태의 번호)

    Returns:
        이슈 객체 또는 None
    """
    project = get_project()
    try:
        return project.issues.get(iid)
    except gitlab.exceptions.GitlabGetError:
        return None


def update_issue_state(iid: int, state_event: str):
    """
    이슈 상태 변경.

    Args:
        iid: 이슈 번호
        state_event: 'close' 또는 'reopen'

    Returns:
        업데이트된 이슈 객체
    """
    project = get_project()
    issue = project.issues.get(iid)
    issue.state_event = state_event
    issue.save()
    return issue


def list_issues(state: str = "opened", per_page: int = 10):
    """
    이슈 목록 조회.

    Args:
        state: 'opened', 'closed', 'all'
        per_page: 페이지당 이슈 수

    Returns:
        이슈 목록
    """
    project = get_project()
    return project.issues.list(state=state, per_page=per_page)
