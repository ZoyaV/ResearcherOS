"""Contracts for project-level sync and discovery orchestration."""

from pathlib import Path

from koi.projects import sync as project_sync


def test_pull_projects_injects_discovery_callback(monkeypatch) -> None:
    calls: list[dict] = []

    def pull_projects(**kwargs) -> dict:
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(project_sync.project_sync, "pull_projects", pull_projects)

    assert project_sync.pull_projects(dry_run=True, project_id="demo") == {"ok": True}
    assert calls == [
        {
            "dry_run": True,
            "project_id": "demo",
            "discover_ref_changes": project_sync._discover_ref_changes,
        }
    ]


def test_discover_ref_changes_appends_detected_items(monkeypatch) -> None:
    items = [{"key": "demo:rq-1:sig"}]
    appended: list[list[dict]] = []
    monkeypatch.setattr(
        project_sync.discoveries,
        "detect_rq_discoveries",
        lambda old_ref, new_ref, *, repo_root: items,
    )
    monkeypatch.setattr(
        project_sync,
        "append_discoveries",
        lambda discoveries: appended.append(discoveries),
    )

    assert project_sync._discover_ref_changes("old", "new", Path("repo")) == items
    assert appended == [items]


def test_discovery_state_initialization_pins_heads_and_signatures(monkeypatch) -> None:
    saved: list[dict] = []
    monkeypatch.setattr(project_sync.project_sync_queue, "load_state", lambda: {})
    monkeypatch.setattr(
        project_sync.project_sync_queue,
        "save_state",
        lambda state: saved.append(dict(state)),
    )
    monkeypatch.setattr(
        project_sync.project_sync_queue,
        "get_last_rq_head",
        lambda: "head",
    )
    monkeypatch.setattr(
        project_sync.discoveries,
        "current_heads",
        lambda: {"/repo": "head"},
    )
    monkeypatch.setattr(
        project_sync.discoveries,
        "_filesystem_signature_snapshot",
        lambda: {"demo:rq-1": "sig"},
    )

    assert project_sync.ensure_discovery_state_initialized() == "head"
    assert saved[0]["last_rq_heads"] == {"/repo": "head"}
    assert saved[0]["last_rq_sigs"] == {"demo:rq-1": "sig"}
    assert saved[0]["rq_sigs_initialized"] is True
