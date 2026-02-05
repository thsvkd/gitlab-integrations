"""GitLab API client."""

import gitlab

from gitlab_slack.config import settings

# Initialize GitLab client (allow self-signed certificates)
gl = gitlab.Gitlab(
    settings.gitlab_url,
    private_token=settings.gitlab_token,
    ssl_verify=False,
)


def get_project():
    """Return GitLab project object."""
    return gl.projects.get(settings.gitlab_project_id)


def create_issue(title: str, description: str = "", labels: list[str] | None = None):
    """
    Create a new issue in GitLab.

    Args:
        title: Issue title
        description: Issue description
        labels: List of labels

    Returns:
        Created issue object
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
    Get issue by IID (project-level issue number).

    Args:
        iid: Issue number within the project (#123 format)

    Returns:
        Issue object or None
    """
    project = get_project()
    try:
        return project.issues.get(iid)
    except gitlab.exceptions.GitlabGetError:
        return None


def update_issue_state(iid: int, state_event: str):
    """
    Update issue state.

    Args:
        iid: Issue number
        state_event: 'close' or 'reopen'

    Returns:
        Updated issue object
    """
    project = get_project()
    issue = project.issues.get(iid)
    issue.state_event = state_event
    issue.save()
    return issue


def list_issues(state: str = "opened", per_page: int = 10):
    """
    List issues.

    Args:
        state: 'opened', 'closed', 'all'
        per_page: Number of issues per page

    Returns:
        List of issues
    """
    project = get_project()
    return project.issues.list(state=state, per_page=per_page)
