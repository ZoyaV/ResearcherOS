"""Staging and history tests for separate morphology presentations."""

import json

import pytest

from koi.literature import morphology
from koi.literature import morphology_presentation as presentation_service


ARTICLE = """
<article class="ltx_document">
  <section id="S2">
    <p>The method applies one operation.</p>
    <math id="S2.E1.m1" alttext="y=x+1"><mi>y</mi></math>
  </section>
  <section id="S3">
    <p>The measured score improves.</p>
    <figure id="S3.T1" class="ltx_table">
      <figcaption>Table 1 Results</figcaption>
      <table>
        <tr id="S3.T1.r1"><td id="S3.T1.r1.c1">A</td><td id="S3.T1.r1.c2">92</td></tr>
        <tr id="S3.T1.r2"><td id="S3.T1.r2.c1">B</td><td id="S3.T1.r2.c2">88</td></tr>
      </table>
    </figure>
  </section>
</article>
"""


def loc(value: str) -> dict[str, str]:
    return {"en": value, "ru": value}


@pytest.fixture()
def parent_run(tmp_path, monkeypatch):
    root = tmp_path / "koi-structure" / "paper_morphology"
    monkeypatch.setattr(morphology, "paper_morphology_dir", lambda _project_id: root)
    run_id = "morphology_run"
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    graph = {
        "run_id": run_id,
        "nodes": [
            {
                "id": "n01",
                "role": "mechanism",
                "statement": "Method",
                "evidence": [
                    {
                        "quote": "The method applies one operation.",
                        "section": "2 Method",
                    }
                ],
            },
            {
                "id": "n02",
                "role": "result",
                "statement": "Result",
                "evidence": [
                    {
                        "quote": "The measured score improves.",
                        "section": "3 Results",
                    }
                ],
            },
        ],
        "edges": [],
    }
    math = {
        "run_id": run_id,
        "source_math_count": 1,
        "expressions": [
            {
                "id": "mx001",
                "latex": "y=x+1",
                "occurrences": [{"source_anchor": "S2.E1.m1"}],
            }
        ],
    }
    (run_dir / "input.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "paper": {"title": "Demo", "url": "https://arxiv.org/abs/1"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "morphology.json").write_text(json.dumps(graph), encoding="utf-8")
    (run_dir / "math_analysis.json").write_text(json.dumps(math), encoding="utf-8")
    (run_dir / "article.html").write_text(ARTICLE, encoding="utf-8")
    return "demo", run_id, run_dir


def valid_presentation(run_id: str, presentation_run_id: str) -> dict:
    return {
        "version": 1,
        "presentation_run_id": presentation_run_id,
        "morphology_run_id": run_id,
        "default_language": "ru",
        "slides": [
            {
                "id": "cover",
                "kind": "cover",
                "node_ids": [],
                "section_anchor": None,
                "title": loc("Demo"),
                "body": loc("Demo presentation"),
                "evidence_quote": None,
                "visual": None,
            },
            {
                "id": "slide_n01",
                "kind": "node",
                "node_ids": ["n01"],
                "section_anchor": "2 Method",
                "title": loc("Method"),
                "body": loc("Method explanation"),
                "evidence_quote": "The method applies one operation.",
                "visual": None,
            },
            {
                "id": "slide_n01_math",
                "kind": "math",
                "node_ids": ["n01"],
                "section_anchor": "2 Method",
                "title": loc("Method equation"),
                "body": loc("Equation explanation"),
                "evidence_quote": "The method applies one operation.",
                "visual": {"kind": "math", "expression_ids": ["mx001"]},
            },
            {
                "id": "slide_n02",
                "kind": "node",
                "node_ids": ["n02"],
                "section_anchor": "3 Results",
                "title": loc("Result"),
                "body": loc("Result explanation"),
                "evidence_quote": "The measured score improves.",
                "visual": None,
            },
            {
                "id": "slide_n02_table",
                "kind": "table",
                "node_ids": ["n02"],
                "section_anchor": "3 Results",
                "title": loc("Measured result"),
                "body": loc("The highlighted score supports the result"),
                "evidence_quote": "The measured score improves.",
                "visual": {
                    "kind": "table",
                    "table_id": "t01",
                    "source_anchor": "S3.T1",
                    "source_caption": "Table 1 Results",
                    "columns": ["Model", "Score"],
                    "rows": [
                        {
                            "label": "A",
                            "source_anchor": "S3.T1.r1",
                            "cells": [
                                {
                                    "source_anchor": "S3.T1.r1.c2",
                                    "column": "Score",
                                    "value": "92",
                                    "emphasis": "best",
                                    "supports_node_ids": ["n02"],
                                }
                            ],
                        },
                        {
                            "label": "B",
                            "source_anchor": "S3.T1.r2",
                            "cells": [
                                {
                                    "source_anchor": "S3.T1.r2.c2",
                                    "column": "Score",
                                    "value": "88",
                                    "emphasis": "neutral",
                                    "supports_node_ids": [],
                                }
                            ],
                        },
                    ],
                    "highlight_cell_ids": ["S3.T1.r1.c2"],
                    "explanation": loc("A is higher than B"),
                },
            },
        ],
        "coverage": {
            "node_ids": ["n01", "n02"],
            "expression_ids": ["mx001"],
            "figure_ids": [],
            "table_ids": ["t01"],
        },
    }


def valid_critique(presentation_run_id: str, slides: list[dict]) -> dict:
    return {
        "version": 1,
        "presentation_run_id": presentation_run_id,
        "pass": True,
        "slides": [
            {
                "slide_id": slide["id"],
                "pass": True,
                "checks": {
                    "overflow": False,
                    "minimum_font_px": 18,
                    "image_width_fraction": None,
                    "minimum_image_text_px": None,
                    "table_values_grounded": (
                        True if slide["kind"] == "table" else None
                    ),
                    "highlights_support_claim": (
                        True if slide["kind"] == "table" else None
                    ),
                },
                "issues": [],
            }
            for slide in slides
        ],
    }


def test_stage_writes_prompt_input_and_nested_history(parent_run) -> None:
    project, morphology_run_id, _ = parent_run
    staged = presentation_service.stage_morphology_presentation(
        project, morphology_run_id
    )
    run_dir = (
        presentation_service.presentations_dir(project, morphology_run_id)
        / staged["run_id"]
    )
    stored = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    assert stored["required_artifacts"] == [
        "presentation.json",
        "presentation_critique.json",
    ]
    assert stored["source_counts"] == {"nodes": 2, "math_occurrences": 1}
    assert "Cover every node in article order" in staged["prompt"]
    assert "Result nodes require a grounded" in staged["prompt"]
    assert presentation_service.list_presentation_runs(
        project, morphology_run_id
    )[0]["status"] == "staged"


def test_run_is_ready_only_after_presentation_and_passing_critique(parent_run) -> None:
    project, morphology_run_id, _ = parent_run
    staged = presentation_service.stage_morphology_presentation(
        project, morphology_run_id
    )
    run_dir = (
        presentation_service.presentations_dir(project, morphology_run_id)
        / staged["run_id"]
    )
    payload = valid_presentation(morphology_run_id, staged["run_id"])
    (run_dir / "presentation.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    assert presentation_service.load_presentation_run(
        project, morphology_run_id, staged["run_id"]
    )["status"] == "staged"

    critique = valid_critique(staged["run_id"], payload["slides"])
    (run_dir / "presentation_critique.json").write_text(
        json.dumps(critique), encoding="utf-8"
    )
    loaded = presentation_service.load_presentation_run(
        project, morphology_run_id, staged["run_id"]
    )
    assert loaded["status"] == "ready"
    assert loaded["presentation"]["coverage"]["node_ids"] == ["n01", "n02"]


def test_invalid_critique_stops_run(parent_run) -> None:
    project, morphology_run_id, _ = parent_run
    staged = presentation_service.stage_morphology_presentation(
        project, morphology_run_id
    )
    run_dir = (
        presentation_service.presentations_dir(project, morphology_run_id)
        / staged["run_id"]
    )
    payload = valid_presentation(morphology_run_id, staged["run_id"])
    critique = valid_critique(staged["run_id"], payload["slides"])
    critique["pass"] = False
    (run_dir / "presentation.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    (run_dir / "presentation_critique.json").write_text(
        json.dumps(critique), encoding="utf-8"
    )

    loaded = presentation_service.load_presentation_run(
        project, morphology_run_id, staged["run_id"]
    )
    assert loaded["status"] == "invalid"
    assert any("did not pass" in error for error in loaded["validation_errors"])


def test_stage_requires_graph_math_and_html(tmp_path, monkeypatch) -> None:
    root = tmp_path / "koi-structure" / "paper_morphology"
    monkeypatch.setattr(morphology, "paper_morphology_dir", lambda _project_id: root)
    run_dir = root / "incomplete"
    run_dir.mkdir(parents=True)
    (run_dir / "morphology.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Mathematical lessons"):
        presentation_service.stage_morphology_presentation("demo", "incomplete")


def test_latest_run_prefers_ready_over_newer_staged(parent_run) -> None:
    project, morphology_run_id, _ = parent_run
    ready = presentation_service.stage_morphology_presentation(
        project, morphology_run_id
    )
    run_dir = (
        presentation_service.presentations_dir(project, morphology_run_id)
        / ready["run_id"]
    )
    payload = valid_presentation(morphology_run_id, ready["run_id"])
    (run_dir / "presentation.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    (run_dir / "presentation_critique.json").write_text(
        json.dumps(valid_critique(ready["run_id"], payload["slides"])),
        encoding="utf-8",
    )
    presentation_service.stage_morphology_presentation(project, morphology_run_id)
    latest = presentation_service.latest_presentation_run(project, morphology_run_id)
    assert latest["run_id"] == ready["run_id"]
    assert latest["status"] == "ready"


def test_delete_removes_only_selected_presentation(parent_run) -> None:
    project, morphology_run_id, parent_dir = parent_run
    first = presentation_service.stage_morphology_presentation(
        project, morphology_run_id
    )
    second = presentation_service.stage_morphology_presentation(
        project, morphology_run_id
    )
    presentation_service.delete_presentation_run(
        project, morphology_run_id, first["run_id"]
    )
    runs = presentation_service.list_presentation_runs(project, morphology_run_id)
    assert [run["run_id"] for run in runs] == [second["run_id"]]
    assert (parent_dir / "morphology.json").is_file()


def test_presentation_api_stages_from_completed_graph(parent_run) -> None:
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from api.main import app
    from koi.core.models import Project

    project, morphology_run_id, _ = parent_run
    dummy = Project(id=project, title="Demo", path=".", koi_dir=".")
    client = TestClient(app)
    with patch("api.routers.morphology.parse_project", return_value=dummy):
        staged = client.post(
            f"/projects/{project}/morphology/{morphology_run_id}/presentations/stage"
        )
        assert staged.status_code == 200
        run_id = staged.json()["run_id"]
        listed = client.get(
            f"/projects/{project}/morphology/{morphology_run_id}/presentations"
        )
        assert listed.json()["count"] == 1
        loaded = client.get(
            f"/projects/{project}/morphology/{morphology_run_id}/presentations/{run_id}"
        )
        assert loaded.json()["status"] == "staged"
