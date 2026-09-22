from __future__ import annotations

from typing import Any

import pytest

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


def test_gh_decodes_github_output_as_utf8(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class Result:
        returncode = 0
        stdout = "V11 — Pouvoir local et socio-économie"
        stderr = ""

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return Result()

    monkeypatch.setattr(github_backlog.subprocess, "run", fake_run)
    assert "socio-économie" in github_backlog.gh("api", "example")
    assert captured["encoding"] == "utf-8"


def test_gh_retries_transient_network_failures(monkeypatch) -> None:
    attempts = 0
    waits: list[int] = []

    class Result:
        stdout = "ok"
        stderr = ""

        def __init__(self, returncode: int) -> None:
            self.returncode = returncode
            if returncode:
                self.stderr = "net/http: TLS handshake timeout"

    def fake_run(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        return Result(1 if attempts < 3 else 0)

    monkeypatch.setattr(github_backlog.subprocess, "run", fake_run)
    monkeypatch.setattr(github_backlog.time, "sleep", waits.append)
    assert github_backlog.gh("api", "example") == "ok"
    assert attempts == 3
    assert waits == [1, 2]


def test_gh_does_not_retry_functional_failures(monkeypatch) -> None:
    class Result:
        returncode = 1
        stdout = ""
        stderr = "Validation Failed (HTTP 422)"

    monkeypatch.setattr(github_backlog.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(github_backlog.time, "sleep", lambda delay: pytest.fail("unexpected retry"))
    with pytest.raises(RuntimeError, match="Validation Failed"):
        github_backlog.gh("api", "example")


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
