"""Project sync orchestration that connects Git transport and discoveries."""

from __future__ import annotations

from pathlib import Path

from koi.adapters import project_sync, project_sync_queue
from koi.adapters.rq_discoveries_feed import append_discoveries
from koi.projects import discoveries


def _discover_ref_changes(
    old_ref: str,
    new_ref: str,
    repo_root: Path,
) -> list[dict]:
    items = discoveries.detect_rq_discoveries(
        old_ref,
        new_ref,
        repo_root=repo_root,
    )
    if items:
        append_discoveries(items)
    return items


def pull_projects(*, dry_run: bool = False, project_id: str | None = None) -> dict:
    return project_sync.pull_projects(
        dry_run=dry_run,
        project_id=project_id,
        discover_ref_changes=_discover_ref_changes,
    )


def ensure_discovery_state_initialized() -> str | None:
    """Pin current heads/signatures so historical answers are not announced."""
    state = project_sync_queue.load_state()
    if state.get("last_rq_heads") and state.get("rq_sigs_initialized"):
        return project_sync_queue.get_last_rq_head()

    heads = discoveries.current_heads()
    if heads:
        state["last_rq_heads"] = heads
        from koi.adapters.workspace import get_workspace

        engine = str(get_workspace().git_root().resolve())
        if engine in heads:
            state["last_rq_head"] = heads[engine]
    if not state.get("rq_sigs_initialized"):
        state["last_rq_sigs"] = discoveries._filesystem_signature_snapshot()
        state["rq_sigs_initialized"] = True
    project_sync_queue.save_state(state)
    return project_sync_queue.get_last_rq_head()
