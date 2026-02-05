"""
GitLab API client module.

This module provides functions for interacting with the GitLab API,
including issue creation, retrieval, and state management.

Note:
    SSL verification is disabled to support internal GitLab servers
    with self-signed certificates.
"""

from typing import TYPE_CHECKING

import gitlab
from gitlab.v4.objects import Project, ProjectIssue

from gitlab_integrations.config import settings

if TYPE_CHECKING:
    from gitlab.v4.objects import ProjectIssueManager

# Initialize GitLab client (allow self-signed certificates)
gl: gitlab.Gitlab = gitlab.Gitlab(
    settings.gitlab_url,
    private_token=settings.gitlab_token,
    ssl_verify=False,
)


def get_project() -> Project:
    """
    Get the configured GitLab project.

    Returns:
        Project: GitLab project object for the configured project ID.

    Raises:
        gitlab.exceptions.GitlabGetError: If project is not found or access denied.
    """
    return gl.projects.get(settings.gitlab_project_id)


def create_issue(
    title: str,
    description: str = "",
    labels: list[str] | None = None,
) -> ProjectIssue:
    """
    Create a new issue in GitLab.

    Args:
        title: Issue title (required).
        description: Issue description in markdown format.
        labels: List of label names to apply to the issue.

    Returns:
        ProjectIssue: Created issue object containing iid, web_url, etc.

    Raises:
        gitlab.exceptions.GitlabCreateError: If issue creation fails.

    Example:
        >>> issue = create_issue(
        ...     title="Bug: Login fails",
        ...     description="Users cannot login with SSO",
        ...     labels=["type::bug", "priority::high"]
        ... )
        >>> print(f"Created issue #{issue.iid}")
    """
    project = get_project()
    issue: ProjectIssue = project.issues.create({
        "title": title,
        "description": description,
        "labels": labels or [],
    })
    return issue


def get_issue_by_iid(iid: int) -> ProjectIssue | None:
    """
    Get issue by IID (project-level issue number).

    The IID is the project-specific issue number shown as #123 in GitLab,
    not the global issue ID.

    Args:
        iid: Issue number within the project (e.g., 123 for issue #123).

    Returns:
        ProjectIssue: Issue object if found, None if not found.

    Example:
        >>> issue = get_issue_by_iid(123)
        >>> if issue:
        ...     print(f"Issue #{issue.iid}: {issue.title}")
    """
    project = get_project()
    try:
        return project.issues.get(iid)
    except gitlab.exceptions.GitlabGetError:
        return None


def update_issue_state(iid: int, state_event: str) -> ProjectIssue:
    """
    Update issue state (close or reopen).

    Args:
        iid: Issue number within the project.
        state_event: State transition event, either 'close' or 'reopen'.

    Returns:
        ProjectIssue: Updated issue object.

    Raises:
        gitlab.exceptions.GitlabGetError: If issue is not found.
        gitlab.exceptions.GitlabUpdateError: If state update fails.
        ValueError: If state_event is not 'close' or 'reopen'.

    Example:
        >>> issue = update_issue_state(123, "close")
        >>> print(f"Issue #{issue.iid} is now {issue.state}")
    """
    if state_event not in ("close", "reopen"):
        raise ValueError(f"Invalid state_event: {state_event}. Must be 'close' or 'reopen'.")

    project = get_project()
    issue: ProjectIssue = project.issues.get(iid)
    issue.state_event = state_event
    issue.save()
    return issue


def list_issues(
    state: str = "opened",
    per_page: int = 10,
) -> list[ProjectIssue]:
    """
    List issues from the project.

    Args:
        state: Filter by issue state. Options: 'opened', 'closed', 'all'.
        per_page: Maximum number of issues to return (1-100).

    Returns:
        list[ProjectIssue]: List of issue objects matching the filter.

    Example:
        >>> open_issues = list_issues(state="opened", per_page=5)
        >>> for issue in open_issues:
        ...     print(f"#{issue.iid}: {issue.title}")
    """
    project = get_project()
    return list(project.issues.list(state=state, per_page=per_page))


def list_labels() -> list[dict[str, str]]:
    """
    List all labels from the project.

    Returns:
        list[dict[str, str]]: List of label dictionaries with 'name' and 'color' keys.

    Example:
        >>> labels = list_labels()
        >>> for label in labels:
        ...     print(f"{label['name']} ({label['color']})")
    """
    project = get_project()
    labels = project.labels.list(all=True)
    return [{"name": label.name, "color": label.color} for label in labels]


def list_all_issues(state: str = "all") -> list[ProjectIssue]:
    """
    List all issues from the project with pagination.

    Fetches all issues matching the filter by iterating through
    all pages of results.

    Args:
        state: Filter by issue state. Options: 'opened', 'closed', 'all'.

    Returns:
        list[ProjectIssue]: List of all issue objects matching the filter.

    Example:
        >>> all_issues = list_all_issues(state="all")
        >>> print(f"Total issues: {len(all_issues)}")
    """
    project = get_project()
    return list(project.issues.list(state=state, all=True))
