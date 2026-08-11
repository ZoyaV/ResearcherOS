"""Staging and history contracts for the article-morphology flow."""

import json

import pytest

from koi.literature import morphology


@pytest.fixture()
def project(tmp_path, monkeypatch):
    root = tmp_path / "koi-structure" / "paper_morphology"
    monkeypatch.setattr(morphology, "paper_morphology_dir", lambda _project_id: root)
    return "demo"


PAPER = {
    "title": "  Attention Is All You Need ",
    "arxiv_url": "https://arxiv.org/abs/1706.03762",
    "authors": "Vaswani et al.",
    "year": "2017",
    "abstract": "The dominant sequence transduction models...",
}


def test_paper_key_ignores_scheme_case_and_trailing_slash() -> None:
    base = morphology.paper_key("https://arxiv.org/abs/1706.03762")
    assert base == morphology.paper_key("http://ArXiv.org/abs/1706.03762/")
    assert base != morphology.paper_key("https://arxiv.org/abs/1706.03763")


def test_paper_key_falls_back_to_title() -> None:
    assert morphology.paper_key("", "Some Paper") == morphology.paper_key("", "some paper")
    with pytest.raises(ValueError):
        morphology.paper_key("", "")


def test_stage_writes_input_prompt_and_history(project) -> None:
    staged = morphology.stage_paper_morphology(project, PAPER)

    run_dir = morphology.morphology_dir(project) / staged["run_id"]
    stored = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    assert stored["paper"]["title"] == "Attention Is All You Need"
    assert stored["paper"]["year"] == 2017
    assert stored["paper"]["url"] == PAPER["arxiv_url"]

    prompt = (run_dir / "PROMPT.md").read_text(encoding="utf-8")
    assert "article-morphology" in prompt
    assert staged["run_id"] in prompt
    assert staged["cursor_message"] == staged["prompt"]

    runs = morphology.list_morphology_runs(project)
    assert [row["run_id"] for row in runs] == [staged["run_id"]]
    assert runs[0]["status"] == "staged"


def test_stage_requires_a_title_or_url(project) -> None:
    with pytest.raises(ValueError):
        morphology.stage_paper_morphology(project, {"authors": "Nobody"})


def test_run_turns_ready_when_agent_writes_morphology(project) -> None:
    staged = morphology.stage_paper_morphology(project, PAPER)
    run_dir = morphology.morphology_dir(project) / staged["run_id"]
    graph = {
        "paper_title": "Attention Is All You Need",
        "run_id": staged["run_id"],
        "source_coverage": "full_text",
        "nodes": [{"id": "n01", "role": "problem", "statement": "s", "grounding": "quoted"}],
        "edges": [],
        "entry_node_ids": ["n01"],
    }
    (run_dir / "morphology.json").write_text(json.dumps(graph), encoding="utf-8")
    (run_dir / "report.md").write_text("# Morphology\n", encoding="utf-8")

    assert morphology.list_morphology_runs(project)[0]["status"] == "ready"

    loaded = morphology.load_morphology_run(project, staged["run_id"])
    assert loaded["status"] == "ready"
    assert loaded["morphology"]["nodes"][0]["id"] == "n01"
    assert loaded["report_markdown"].startswith("# Morphology")
    assert loaded["paper"]["title"] == "Attention Is All You Need"


def test_history_keeps_earlier_runs_for_the_same_paper(project) -> None:
    first = morphology.stage_paper_morphology(project, PAPER)
    second = morphology.stage_paper_morphology(project, PAPER)

    assert first["run_id"] != second["run_id"]
    assert first["paper_key"] == second["paper_key"]
    assert {row["run_id"] for row in morphology.list_morphology_runs(project)} == {
        first["run_id"],
        second["run_id"],
    }


def test_list_filters_by_paper_key(project) -> None:
    first = morphology.stage_paper_morphology(project, PAPER)
    other = morphology.stage_paper_morphology(
        project, {"title": "Другая статья", "url": "https://arxiv.org/abs/2001.00001"}
    )

    filtered = morphology.list_morphology_runs(project, paper_key_filter=first["paper_key"])
    assert [row["run_id"] for row in filtered] == [first["run_id"]]
    assert other["paper_key"] != first["paper_key"]


def test_delete_removes_run_dir_and_history(project) -> None:
    staged = morphology.stage_paper_morphology(project, PAPER)
    run_dir = morphology.morphology_dir(project) / staged["run_id"]

    assert morphology.delete_morphology_run(project, staged["run_id"])["removed"] == "run_dir"
    assert not run_dir.exists()
    assert morphology.list_morphology_runs(project) == []

    with pytest.raises(LookupError):
        morphology.delete_morphology_run(project, staged["run_id"])
    with pytest.raises(ValueError):
        morphology.delete_morphology_run(project, "  ")


def test_load_returns_none_for_unknown_run(project) -> None:
    assert morphology.load_morphology_run(project, "nope") is None


def test_article_marks_quotes_from_source_text(project) -> None:
    staged = morphology.stage_paper_morphology(project, PAPER)
    run_dir = morphology.morphology_dir(project) / staged["run_id"]
    source = (
        "Attention Is All You Need\n\n"
        "Abstract\n"
        "The dominant sequence transduction models are based on complex recurrent "
        "or convolutional neural networks.\n\n"
        "1 Introduction\n"
        "Recurrent models typically factor computation along the symbol positions "
        "of the input and output sequences.\n"
    )
    (run_dir / "source_normalized.txt").write_text(source, encoding="utf-8")
    graph = {
        "paper_title": "Attention Is All You Need",
        "run_id": staged["run_id"],
        "source_coverage": "full_text",
        "nodes": [
            {
                "id": "n01",
                "role": "problem",
                "statement": "Seq2seq is RNN/CNN-heavy.",
                "grounding": "quoted",
                "evidence": [
                    {
                        "quote": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
                        "section": "Abstract",
                        "locator": "sentence 1",
                    }
                ],
            },
            {
                "id": "n02",
                "role": "origin",
                "statement": "RNNs factor along positions.",
                "grounding": "quoted",
                "evidence": [
                    {
                        "quote": "Recurrent models typically factor computation along the symbol positions of the input and output sequences.",
                        "section": "1 Introduction",
                        "locator": "para 1",
                    }
                ],
            },
        ],
        "edges": [],
        "entry_node_ids": ["n01"],
    }
    (run_dir / "morphology.json").write_text(
        __import__("json").dumps(graph), encoding="utf-8"
    )

    loaded = morphology.load_morphology_run(project, staged["run_id"])
    assert loaded["has_article"] is True

    article = morphology.build_morphology_article(project, staged["run_id"])
    assert article["available"] is True
    assert article["kind"] == "text"
    assert article["marked_count"] == 2
    assert article["mark_total"] == 2
    assert 'data-node-id="n01"' in article["html"]
    assert 'data-node-id="n02"' in article["html"]
    assert '<h2 class="morph-art-h"' in article["html"]
    assert "Abstract" in article["html"]


def test_article_unavailable_without_source(project) -> None:
    staged = morphology.stage_paper_morphology(project, PAPER)
    article = morphology.build_morphology_article(project, staged["run_id"])
    assert article["available"] is False
    assert article["reason"] == "no_source"
