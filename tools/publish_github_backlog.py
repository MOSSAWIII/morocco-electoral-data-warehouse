from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "metadata" / "github_backlog.json"


def gh(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["gh", *args],
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"gh {' '.join(args)} a échoué")
    return result.stdout


def load_backlog() -> dict:
    return json.loads(BACKLOG.read_text(encoding="utf-8"))


def ensure_labels(repo: str, backlog: dict) -> None:
    for label in backlog["labels"]:
        gh(
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
        )


def ensure_milestones(repo: str, backlog: dict) -> None:
    existing = json.loads(gh("api", f"repos/{repo}/milestones?state=all&per_page=100"))
    titles = {item["title"] for item in existing}
    for milestone in backlog["milestones"]:
        if milestone["title"] not in titles:
            gh(
                "api",
                f"repos/{repo}/milestones",
                "--method",
                "POST",
                "--field",
                f"title={milestone['title']}",
                "--field",
                f"description={milestone['description']}",
            )


def issue_body(issue: dict) -> str:
    lines = ["## Critères d’acceptation", ""]
    lines.extend(f"- [ ] {criterion}" for criterion in issue["acceptance"])
    if issue["depends_on"]:
        lines.extend(["", "## Dépendances", ""])
        lines.extend(f"- {title}" for title in issue["depends_on"])
    lines.extend(["", "_Créé depuis `metadata/github_backlog.json`._", ""])
    return "\n".join(lines)


def ensure_issues(repo: str, backlog: dict) -> None:
    existing = json.loads(gh("issue", "list", "--repo", repo, "--state", "all", "--limit", "1000", "--json", "title"))
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
            issue_body(issue),
            "--milestone",
            issue["milestone"],
        ]
        for label in issue["labels"]:
            args.extend(["--label", label])
        gh(*args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publie le backlog versionné dans un dépôt GitHub déjà créé.")
    parser.add_argument("--repo", help="OWNER/REPO ; utilise la valeur du manifeste par défaut")
    args = parser.parse_args()
    backlog = load_backlog()
    repo = args.repo or backlog["repository"]
    gh("auth", "status", "--hostname", "github.com")
    gh("repo", "view", repo, "--json", "nameWithOwner")
    ensure_labels(repo, backlog)
    ensure_milestones(repo, backlog)
    ensure_issues(repo, backlog)
    print(f"GITHUB_BACKLOG_OK repo={repo} milestones={len(backlog['milestones'])} issues={len(backlog['issues'])}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"GITHUB_BACKLOG_FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

