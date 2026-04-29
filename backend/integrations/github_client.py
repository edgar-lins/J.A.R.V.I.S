from github import Github, Auth
from config import get_settings

settings = get_settings()

_client: Github | None = None


def _get_client() -> Github:
    global _client
    if _client is None:
        if not settings.github_token:
            raise RuntimeError("GITHUB_TOKEN não configurado no .env")
        _client = Github(auth=Auth.Token(settings.github_token))
    return _client


def get_my_prs(state: str = "open") -> list[dict]:
    """Retorna PRs do usuário (abertos por padrão)."""
    gh = _get_client()
    user = gh.get_user(settings.github_username)
    prs = []
    for pr in gh.search_issues(
        f"is:pr author:{settings.github_username} is:{state}",
        sort="updated",
    ):
        prs.append({
            "number": pr.number,
            "title": pr.title,
            "repo": pr.repository.full_name,
            "state": pr.state,
            "url": pr.html_url,
            "updated_at": pr.updated_at.isoformat(),
            "body_preview": (pr.body or "")[:300],
        })
    return prs[:10]


def get_my_issues(state: str = "open") -> list[dict]:
    """Retorna issues atribuídas ao usuário."""
    gh = _get_client()
    issues = []
    for issue in gh.search_issues(
        f"is:issue assignee:{settings.github_username} is:{state}",
        sort="updated",
    ):
        issues.append({
            "number": issue.number,
            "title": issue.title,
            "repo": issue.repository.full_name,
            "state": issue.state,
            "url": issue.html_url,
            "updated_at": issue.updated_at.isoformat(),
        })
    return issues[:10]


def get_notifications(only_unread: bool = True) -> list[dict]:
    """Retorna notificações do GitHub."""
    gh = _get_client()
    notifications = []
    for notif in gh.get_user().get_notifications(all=not only_unread):
        notifications.append({
            "id": notif.id,
            "repo": notif.repository.full_name,
            "type": notif.subject.type,
            "title": notif.subject.title,
            "reason": notif.reason,
            "unread": notif.unread,
            "updated_at": notif.updated_at.isoformat(),
        })
    return notifications[:15]


def get_pr_details(repo_full_name: str, pr_number: int) -> dict:
    """Retorna detalhes de um PR específico incluindo arquivos alterados."""
    gh = _get_client()
    repo = gh.get_repo(repo_full_name)
    pr = repo.get_pull(pr_number)

    files = [
        {"filename": f.filename, "status": f.status, "additions": f.additions, "deletions": f.deletions}
        for f in pr.get_files()
    ][:20]

    reviews = [
        {"user": r.user.login, "state": r.state, "submitted_at": r.submitted_at.isoformat()}
        for r in pr.get_reviews()
    ]

    return {
        "number": pr.number,
        "title": pr.title,
        "state": pr.state,
        "author": pr.user.login,
        "base": pr.base.ref,
        "head": pr.head.ref,
        "mergeable": pr.mergeable,
        "url": pr.html_url,
        "body": (pr.body or "")[:1000],
        "files_changed": files,
        "reviews": reviews,
        "comments": pr.comments,
        "created_at": pr.created_at.isoformat(),
        "updated_at": pr.updated_at.isoformat(),
    }


def format_prs_for_jarvis(prs: list[dict]) -> str:
    if not prs:
        return "Nenhum PR encontrado."
    lines = []
    for pr in prs:
        lines.append(f"- #{pr['number']} [{pr['repo']}] {pr['title']} ({pr['state']}) → {pr['url']}")
    return "\n".join(lines)


def format_notifications_for_jarvis(notifs: list[dict]) -> str:
    if not notifs:
        return "Nenhuma notificação."
    lines = []
    for n in notifs:
        unread = "🔴" if n["unread"] else "⚪"
        lines.append(f"{unread} [{n['repo']}] {n['type']}: {n['title']} (motivo: {n['reason']})")
    return "\n".join(lines)
