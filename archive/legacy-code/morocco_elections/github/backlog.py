from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Any

from morocco_elections.config import get_paths

ROOT = get_paths().project_root
BACKLOG = get_paths().github_backlog


def gh(*args: str, input_text: str | None = None) -> str:
    transient_markers = ("tls handshake timeout", "unexpected eof", "connection reset", "connection attempt failed")
    for attempt in range(4):
        result = subprocess.run(
            ["gh", *args],
            cwd=ROOT,
            input=input_text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout
        message = result.stderr.strip() or result.stdout.strip() or f"gh {' '.join(args)} a échoué"
        if attempt == 3 or not any(marker in message.casefold() for marker in transient_markers):
            raise RuntimeError(message)
        time.sleep(2**attempt)
    raise AssertionError("Boucle de relance GitHub incomplète")


def mutate(*args: str, dry_run: bool) -> str:
    if dry_run:
        print("DRY_RUN " + subprocess.list2cmdline(["gh", *args]))
        return ""
    return gh(*args)


def load_backlog() -> dict[str, Any]:
    return json.loads(BACKLOG.read_text(encoding="utf-8"))


def ensure_labels(repo: str, backlog: dict[str, Any], *, dry_run: bool) -> None:
    for label in backlog["labels"]:
        mutate(
            "label",
            "create",
            label["name"],
            "--repo",
            repo,
            "--color",
            label["color"],
            "--description",
            label["description"],
            "--force",
            dry_run=dry_run,
        )


def ensure_milestones(repo: str, backlog: dict[str, Any], *, dry_run: bool) -> None:
    existing = json.loads(gh("api", f"repos/{repo}/milestones?state=all&per_page=100"))
    by_title = {item["title"]: item for item in existing}
    for milestone in backlog["milestones"]:
        current = by_title.get(milestone["title"])
        fields = (
            "--field",
            f"title={milestone['title']}",
            "--field",
            f"description={milestone['description']}",
            "--field",
            f"state={milestone['state']}",
        )
        if current:
            mutate(
                "api",
                f"repos/{repo}/milestones/{current['number']}",
                "--method",
                "PATCH",
                *fields,
                dry_run=dry_run,
            )
        else:
            mutate("api", f"repos/{repo}/milestones", "--method", "POST", *fields, dry_run=dry_run)


def list_issues(repo: str) -> list[dict[str, Any]]:
    return json.loads(
        gh(
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,title,state,url,labels,milestone",
        )
    )


def issue_body(issue: dict[str, Any], issue_urls: dict[str, str]) -> str:
    lines = ["## Critères d’acceptation", ""]
    marker = "x" if issue["state"] == "closed" and issue["close_reason"] == "completed" else " "
    lines.extend(f"- [{marker}] {criterion}" for criterion in issue["acceptance"])
    for heading, field in (("Dépendances", "depends_on"), ("Bloque", "blocks")):
        if not issue[field]:
            continue
        lines.extend(["", f"## {heading}", ""])
        for title in issue[field]:
            url = issue_urls.get(title)
            lines.append(f"- [{title}]({url})" if url else f"- {title}")
    lines.extend(["", "_Synchronisé depuis `metadata/github_backlog.json`._", ""])
    return "\n".join(lines)


def _create_missing_issues(repo: str, backlog: dict[str, Any], existing: list[dict[str, Any]], *, dry_run: bool) -> None:
    titles = {item["title"] for item in existing}
    for issue in backlog["issues"]:
        if issue["title"] in titles:
            continue
        args = [
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            issue["title"],
            "--body",
            issue_body(issue, {}),
        ]
        for label in issue["labels"]:
            args.extend(["--label", label])
        mutate(*args, dry_run=dry_run)


def _sync_issue(
    repo: str,
    issue: dict[str, Any],
    current: dict[str, Any],
    issue_urls: dict[str, str],
    milestone_number: int,
    *,
    dry_run: bool,
) -> None:
    number = str(current["number"])
    desired_labels = set(issue["labels"])
    current_labels = {item["name"] for item in current.get("labels", [])}
    args = [
        "issue",
        "edit",
        number,
        "--repo",
        repo,
        "--title",
        issue["title"],
        "--body",
        issue_body(issue, issue_urls),
    ]
    for label in sorted(desired_labels - current_labels):
        args.extend(["--add-label", label])
    for label in sorted(current_labels - desired_labels):
        args.extend(["--remove-label", label])
    mutate(*args, dry_run=dry_run)
    mutate(
        "api",
        f"repos/{repo}/issues/{number}",
        "--method",
        "PATCH",
        "--field",
        f"milestone={milestone_number}",
        dry_run=dry_run,
    )
    if issue["state"] == "closed" and current["state"].lower() != "closed":
        mutate("issue", "close", number, "--repo", repo, "--reason", issue["close_reason"], dry_run=dry_run)
    elif issue["state"] == "open" and current["state"].lower() != "open":
        mutate("issue", "reopen", number, "--repo", repo, dry_run=dry_run)


def ensure_issues(repo: str, backlog: dict[str, Any], *, dry_run: bool) -> None:
    existing = list_issues(repo)
    _create_missing_issues(repo, backlog, existing, dry_run=dry_run)
    if dry_run:
        return
    existing = list_issues(repo)
    by_title = {item["title"]: item for item in existing}
    issue_urls = {title: item["url"] for title, item in by_title.items()}
    milestones = json.loads(gh("api", f"repos/{repo}/milestones?state=all&per_page=100"))
    milestone_numbers = {item["title"]: item["number"] for item in milestones}
    for issue in backlog["issues"]:
        current = by_title.get(issue["title"])
        if not current:
            raise RuntimeError(f"Issue absente après création: {issue['title']}")
        milestone_number = milestone_numbers.get(issue["milestone"])
        if milestone_number is None:
            raise RuntimeError(f"Jalon absent après création: {issue['milestone']}")
        _sync_issue(repo, issue, current, issue_urls, milestone_number, dry_run=False)


def publish(repo: str | None = None, *, dry_run: bool = False) -> int:
    backlog = load_backlog()
    selected_repo = repo or backlog["repository"]
    gh("auth", "status", "--hostname", "github.com")
    gh("repo", "view", selected_repo, "--json", "nameWithOwner")
    ensure_labels(selected_repo, backlog, dry_run=dry_run)
    ensure_milestones(selected_repo, backlog, dry_run=dry_run)
    ensure_issues(selected_repo, backlog, dry_run=dry_run)
    status = "GITHUB_BACKLOG_DRY_RUN" if dry_run else "GITHUB_BACKLOG_OK"
    print(f"{status} repo={selected_repo} milestones={len(backlog['milestones'])} issues={len(backlog['issues'])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publie le backlog versionné dans un dépôt GitHub déjà créé.")
    parser.add_argument("--repo", help="OWNER/REPO ; utilise la valeur du manifeste par défaut")
    parser.add_argument("--dry-run", action="store_true", help="Affiche les mutations prévues sans les exécuter")
    args = parser.parse_args(argv)
    return publish(args.repo, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"GITHUB_BACKLOG_FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
