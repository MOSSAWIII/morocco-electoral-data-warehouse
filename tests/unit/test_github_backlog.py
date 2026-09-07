from __future__ import annotations

from typing import Any

from morocco_elections.github import backlog as github_backlog


def issue(title: str, *, state: str = "open", depends_on: list[str] | None = None, blocks: list[str] | None = None) -> dict[str, Any]:
    return {
        "title": title,
        "state": state,
        "close_reason": "completed" if state == "closed" else None,
        "milestone": "V11",
        "labels": ["qa"],
        "depends_on": depends_on or [],
        "blocks": blocks or [],
        "acceptance": ["Critère synthétique"],
    }


def remote(number: int, title: str, *, state: str = "OPEN", labels: list[str] | None = None) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "state": state,
        "url": f"https://example.invalid/issues/{number}",
        "labels": [{"name": label} for label in labels or []],
        "milestone": {"title": "V11"},
    }


def test_missing_issue_creation_is_idempotent(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(github_backlog, "mutate", lambda *args, **kwargs: calls.append(args) or "")
    desired = {"issues": [issue("A"), issue("B")]}
    github_backlog._create_missing_issues("owner/repo", desired, [remote(1, "A")], dry_run=False)
    assert len(calls) == 1 and "B" in calls[0]
    assert "--milestone" not in calls[0]
    calls.clear()
    github_backlog._create_missing_issues("owner/repo", desired, [remote(1, "A"), remote(2, "B")], dry_run=False)
    assert calls == []


def test_issue_sync_updates_links_labels_and_closes(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(github_backlog, "mutate", lambda *args, **kwargs: calls.append(args) or "")
    desired = issue("A", state="closed", depends_on=["B"], blocks=["C"])
    github_backlog._sync_issue(
        "owner/repo",
        desired,
        remote(1, "A", labels=["old"]),
        {"B": "https://example.invalid/issues/2", "C": "https://example.invalid/issues/3"},
        2,
        dry_run=False,
    )
    rendered = " ".join(calls[0])
    assert "https://example.invalid/issues/2" in rendered
    assert "https://example.invalid/issues/3" in rendered
    assert "--add-label qa" in rendered and "--remove-label old" in rendered
    assert calls[1][0] == "api" and "milestone=2" in calls[1]
    assert calls[2][:2] == ("issue", "close")


def test_issue_sync_reopens_a_closed_issue(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(github_backlog, "mutate", lambda *args, **kwargs: calls.append(args) or "")
    github_backlog._sync_issue(
        "owner/repo", issue("A"), remote(1, "A", state="CLOSED", labels=["qa"]), {}, 2, dry_run=False
    )
    assert calls[-1][:2] == ("issue", "reopen")


def test_milestones_are_created_or_updated(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        github_backlog,
        "gh",
        lambda *args, **kwargs: '[{"number":1,"title":"V10","state":"open"}]',
    )
    monkeypatch.setattr(github_backlog, "mutate", lambda *args, **kwargs: calls.append(args) or "")
    desired = {
        "milestones": [
            {"title": "V10", "description": "Terminé", "state": "closed"},
            {"title": "V11", "description": "À faire", "state": "open"},
        ]
    }
    github_backlog.ensure_milestones("owner/repo", desired, dry_run=False)
    assert any("PATCH" in call for call in calls)
    assert any("POST" in call for call in calls)
