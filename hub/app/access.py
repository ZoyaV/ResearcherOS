"""Project visibility helpers for Hub."""

from __future__ import annotations

from typing import Optional

from hub.app.store import HubProject, HubStore


def _has_valid_unlisted_bookmark(
    project: HubProject, viewer_github_id: int, store: HubStore
) -> bool:
    """True if the viewer bookmarked this unlisted project with a matching token."""
    if not project.secret_token:
        return False
    for bookmark in store.user_bookmarks(viewer_github_id):
        if bookmark.get("slug") != project.slug:
            continue
        if (bookmark.get("token") or "") == project.secret_token:
            return True
    return False


def can_view_project_with_store(
    project: HubProject,
    viewer_github_id: Optional[int],
    store: HubStore,
    *,
    token: Optional[str] = None,
) -> bool:
    if not project.enabled and viewer_github_id != project.owner_github_id:
        return False
    if project.visibility == "public":
        return True
    if project.visibility == "unlisted":
        if viewer_github_id is not None and viewer_github_id == project.owner_github_id:
            return True
        if token and token == project.secret_token:
            return True
        if viewer_github_id is not None and _has_valid_unlisted_bookmark(
            project, viewer_github_id, store
        ):
            return True
        return False
    if project.visibility == "network" and viewer_github_id is not None:
        if viewer_github_id == project.owner_github_id:
            return True
        return project.owner_github_id in store.following_ids(viewer_github_id)
    return False


def is_project_listed(project: HubProject) -> bool:
    """Shown in Explore / network feeds (not direct owner preview)."""
    return bool(project.enabled)
