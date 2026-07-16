"""Hub /projects/grouped respects research programs from project frontmatter."""

from __future__ import annotations

from types import SimpleNamespace

from hub.app.koi_readonly import projects_grouped


class _FakeStore:
    def __init__(self, projects: list, snapshots: dict):
        self._projects = projects
        self._snapshots = snapshots

    def list_projects(self):
        return self._projects

    def get_snapshot(self, slug: str):
        return self._snapshots.get(slug)


def _hub_project(**kwargs):
    defaults = {
        "slug": "slug",
        "owner_github_id": 1,
        "owner_login": "zoya",
        "repo_full_name": "org/repo",
        "branch": "koi/research",
        "title": "Title",
        "visibility": "public",
        "secret_token": "",
        "composite_id": "",
        "programs": [],
        "enabled": True,
        "last_sync_at": "",
        "last_commit": "",
        "created_at": "",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_projects_grouped_by_program(monkeypatch):
    prog = [
        {
            "id": "мультимодальное-обучение-с-подкреплением",
            "title": "Мультимодальное обучение с подкреплением",
            "description": "",
        }
    ]
    th = _hub_project(
        slug="TalkingHeads",
        title="TalkingHeads",
        composite_id="llm-ood-decision-making",
        programs=prog,
    )
    verl = _hub_project(
        slug="verl",
        title="verl",
        composite_id="llm-ood-decision-making",
        programs=prog,
    )
    bike = _hub_project(
        slug="bike",
        title="bike",
        programs=[
            {
                "id": "obuchenie-na-platforme-researchos",
                "title": "Обучение на платформе ResearchOS",
                "description": "",
            }
        ],
    )

    snapshots = {
        "TalkingHeads": {
            "meta": {"programs": prog, "composite_id": "llm-ood-decision-making"},
            "project": {
                "id": "talking-heads",
                "title": "TalkingHeads",
                "nodes": [
                    {
                        "id": "problem",
                        "node_type": "problem",
                        "title": "Проблема обучения LLM принятию решений в OOD средах",
                        "parent_id": None,
                        "description": "",
                        "verdict": "open",
                        "research_questions": [],
                        "project_id": "talking-heads",
                    }
                ],
                "boards": {},
            },
        },
        "verl": {
            "meta": {"programs": prog, "composite_id": "llm-ood-decision-making"},
            "project": {
                "id": "verl-agent-craftext",
                "title": "verl",
                "nodes": [
                    {
                        "id": "problem",
                        "node_type": "problem",
                        "title": "Проблема обучения LLM принятию решений в OOD средах",
                        "parent_id": None,
                        "description": "",
                        "verdict": "open",
                        "research_questions": [],
                        "project_id": "verl-agent-craftext",
                    }
                ],
                "boards": {},
            },
        },
        "bike": {
            "meta": {},
            "project": {
                "id": "bicycle-ads-efficiency",
                "title": "bike",
                "nodes": [
                    {
                        "id": "p1",
                        "node_type": "problem",
                        "title": "Ads",
                        "parent_id": None,
                        "description": "",
                        "verdict": "open",
                        "research_questions": [],
                        "project_id": "bicycle-ads-efficiency",
                    }
                ],
                "boards": {},
            },
        },
    }
    store = _FakeStore([th, verl, bike], snapshots)

    class _Req:
        app = SimpleNamespace(
            state=SimpleNamespace(
                hub_config=SimpleNamespace(),
                hub_store=store,
            )
        )

    monkeypatch.setattr(
        "hub.app.koi_readonly.get_session", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "hub.app.koi_readonly.can_view_project_with_store",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "hub.app.koi_readonly.dedupe_hub_projects",
        lambda projects: projects,
    )

    grouped = projects_grouped(_Req())
    group_ids = {g["id"] for g in grouped["groups"]}
    assert "мультимодальное-обучение-с-подкреплением" in group_ids
    assert "obuchenie-na-platforme-researchos" in group_ids

    mm = next(
        g
        for g in grouped["groups"]
        if g["id"] == "мультимодальное-обучение-с-подкреплением"
    )
    assert len(mm["composites"]) == 1
    assert mm["composites"][0]["id"] == "llm-ood-decision-making"
    # Member projects hidden when composite exists
    assert mm["projects"] == []

    bike_group = next(
        g for g in grouped["groups"] if g["id"] == "obuchenie-na-platforme-researchos"
    )
    assert [p["id"] for p in bike_group["projects"]] == ["bicycle-ads-efficiency"]
