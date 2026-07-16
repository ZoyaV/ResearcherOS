"""Hub composite grouping: same problem title unifies explicit + auto keys."""

from __future__ import annotations

from types import SimpleNamespace

from hub.app.hub_composite import list_hub_composites, load_hub_composite


def _hub(slug: str, composite_id: str = "", programs: list | None = None):
    return SimpleNamespace(
        slug=slug,
        title=slug,
        composite_id=composite_id,
        programs=programs or [],
    )


def _project(project_id: str, problem_title: str, extra_nodes: list | None = None):
    nodes = [
        {
            "id": "problem",
            "project_id": project_id,
            "parent_id": None,
            "node_type": "problem",
            "title": problem_title,
            "description": "",
            "verdict": "open",
            "research_questions": [],
        },
        {
            "id": "c-shared",
            "project_id": project_id,
            "parent_id": "problem",
            "node_type": "cause",
            "title": "Shared cause",
            "description": "",
            "verdict": "open",
            "research_questions": [],
        },
    ]
    if extra_nodes:
        nodes.extend(extra_nodes)
    return {
        "id": project_id,
        "title": project_id,
        "description": "",
        "literature_keywords": [],
        "card_tags": [],
        "nodes": nodes,
        "boards": {},
    }


def test_hub_groups_explicit_and_auto_composite_by_problem_title():
    problem = "Проблема обучения LLM принятию решений в OOD средах"
    talking = _project(
        "talking-heads",
        problem,
        [
            {
                "id": "r-oracle",
                "project_id": "talking-heads",
                "parent_id": "c-shared",
                "node_type": "remediation",
                "title": "External operator",
                "description": "",
                "verdict": "open",
                "research_questions": [],
            }
        ],
    )
    verl = _project(
        "verl-agent-craftext",
        problem,
        [
            {
                "id": "r-div",
                "project_id": "verl-agent-craftext",
                "parent_id": "c-shared",
                "node_type": "remediation",
                "title": "Diversity bonus",
                "description": "",
                "verdict": "open",
                "research_questions": [],
            }
        ],
    )
    members = [
        (_hub("TalkingHeads", ""), talking),
        (_hub("verl", "llm-ood-decision-making"), verl),
    ]

    summaries = list_hub_composites(members)
    assert len(summaries) == 1
    assert summaries[0]["id"] == "llm-ood-decision-making"
    assert set(summaries[0]["member_ids"]) == {"talking-heads", "verl-agent-craftext"}

    payload = load_hub_composite(store=None, composite_id="llm-ood-decision-making", members=members)
    assert payload is not None
    assert payload["is_composite"] is True
    ids = {n["id"] for n in payload["nodes"]}
    assert ids == {"problem", "c-shared", "r-oracle", "r-div"}


def test_hub_composites_include_member_programs():
    problem = "Shared problem"
    prog = [
        {
            "id": "мультимодальное-обучение-с-подкреплением",
            "title": "Мультимодальное обучение с подкреплением",
            "description": "",
        }
    ]
    a = _project("proj-a", problem)
    b = _project("proj-b", problem)
    members = [
        (_hub("a", programs=prog), a),
        (_hub("b", composite_id="shared", programs=prog), b),
    ]
    summaries = list_hub_composites(members)
    assert summaries[0]["programs"] == ["мультимодальное-обучение-с-подкреплением"]
