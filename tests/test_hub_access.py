"""Hub access: unlisted projects via owner, token, or bookmark."""

from __future__ import annotations

from types import SimpleNamespace

from hub.app.access import can_view_project_with_store
from hub.app.koi_readonly import _viewable_members


class _Store:
    def __init__(
        self,
        *,
        bookmarks: list[dict] | None = None,
        following: set[int] | None = None,
        projects: list | None = None,
        snapshots: dict | None = None,
    ):
        self._bookmarks = bookmarks or []
        self._following = following or set()
        self._projects = projects or []
        self._snapshots = snapshots or {}

    def user_bookmarks(self, user_id: int):
        return [
            {"slug": str(r["slug"]), "token": str(r.get("token") or "")}
            for r in self._bookmarks
            if r.get("user_id") == user_id
        ]

    def following_ids(self, follower_id: int):
        return set(self._following)

    def list_projects(self):
        return self._projects

    def get_snapshot(self, slug: str):
        return self._snapshots.get(slug)


def _project(**kwargs):
    defaults = {
        "slug": "secret-lab",
        "owner_github_id": 10,
        "visibility": "unlisted",
        "secret_token": "tok-abc",
        "enabled": True,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_unlisted_denied_without_access():
    store = _Store()
    assert not can_view_project_with_store(_project(), viewer_github_id=99, store=store)


def test_unlisted_owner_can_view():
    store = _Store()
    assert can_view_project_with_store(_project(), viewer_github_id=10, store=store)


def test_unlisted_valid_token_can_view():
    store = _Store()
    assert can_view_project_with_store(
        _project(), viewer_github_id=None, store=store, token="tok-abc"
    )
    assert not can_view_project_with_store(
        _project(), viewer_github_id=None, store=store, token="wrong"
    )


def test_unlisted_bookmark_with_matching_token_can_view():
    store = _Store(
        bookmarks=[{"user_id": 42, "slug": "secret-lab", "token": "tok-abc"}]
    )
    assert can_view_project_with_store(_project(), viewer_github_id=42, store=store)


def test_unlisted_bookmark_with_wrong_token_denied():
    store = _Store(
        bookmarks=[{"user_id": 42, "slug": "secret-lab", "token": "stale"}]
    )
    assert not can_view_project_with_store(_project(), viewer_github_id=42, store=store)


def test_viewable_members_includes_bookmarked_unlisted(monkeypatch):
    hub = _project(
        slug="secret-lab",
        title="Secret",
        owner_login="alice",
        repo_full_name="alice/secret",
        branch="koi/research",
        composite_id="",
        programs=[],
        last_sync_at="",
        last_commit="",
        created_at="",
    )
    public = _project(
        slug="open",
        title="Open",
        visibility="public",
        secret_token="",
        owner_github_id=1,
        owner_login="bob",
        repo_full_name="bob/open",
        branch="koi/research",
        composite_id="",
        programs=[],
        last_sync_at="",
        last_commit="",
        created_at="",
    )
    store = _Store(
        projects=[hub, public],
        bookmarks=[{"user_id": 42, "slug": "secret-lab", "token": "tok-abc"}],
        snapshots={
            "secret-lab": {"project": {"id": "secret-lab", "title": "Secret"}},
            "open": {"project": {"id": "open", "title": "Open"}},
        },
    )

    class _Req:
        app = SimpleNamespace(
            state=SimpleNamespace(hub_config=SimpleNamespace(), hub_store=store)
        )

    monkeypatch.setattr(
        "hub.app.koi_readonly.get_session",
        lambda *args, **kwargs: SimpleNamespace(github_id=42),
    )
    monkeypatch.setattr(
        "hub.app.koi_readonly.dedupe_hub_projects",
        lambda projects: list(projects),
    )

    members = _viewable_members(_Req(), SimpleNamespace(), store)
    slugs = {hp.slug for hp, _ in members}
    assert slugs == {"secret-lab", "open"}


def test_viewable_members_includes_unlisted_with_share_token(monkeypatch):
    hub = _project(
        slug="secret-lab",
        title="Secret",
        owner_login="alice",
        repo_full_name="alice/secret",
        branch="koi/research",
        composite_id="",
        programs=[],
        last_sync_at="",
        last_commit="",
        created_at="",
    )
    store = _Store(
        projects=[hub],
        snapshots={"secret-lab": {"project": {"id": "secret-lab", "title": "Secret"}}},
    )

    class _Req:
        query_params = {"token": "tok-abc"}
        app = SimpleNamespace(
            state=SimpleNamespace(hub_config=SimpleNamespace(), hub_store=store)
        )

    monkeypatch.setattr(
        "hub.app.koi_readonly.get_session",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "hub.app.koi_readonly.dedupe_hub_projects",
        lambda projects: list(projects),
    )

    members = _viewable_members(_Req(), SimpleNamespace(), store)
    assert [hp.slug for hp, _ in members] == ["secret-lab"]


def test_viewable_members_excludes_unlisted_without_bookmark(monkeypatch):
    hub = _project(
        slug="secret-lab",
        title="Secret",
        owner_login="alice",
        repo_full_name="alice/secret",
        branch="koi/research",
        composite_id="",
        programs=[],
        last_sync_at="",
        last_commit="",
        created_at="",
    )
    store = _Store(
        projects=[hub],
        snapshots={"secret-lab": {"project": {"id": "secret-lab", "title": "Secret"}}},
    )

    class _Req:
        query_params = {}
        app = SimpleNamespace(
            state=SimpleNamespace(hub_config=SimpleNamespace(), hub_store=store)
        )

    monkeypatch.setattr(
        "hub.app.koi_readonly.get_session",
        lambda *args, **kwargs: SimpleNamespace(github_id=99),
    )
    monkeypatch.setattr(
        "hub.app.koi_readonly.dedupe_hub_projects",
        lambda projects: list(projects),
    )

    members = _viewable_members(_Req(), SimpleNamespace(), store)
    assert members == []
