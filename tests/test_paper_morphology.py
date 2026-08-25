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
    assert stored["required_artifacts"] == ["morphology.json", "math_analysis.json"]

    prompt = (run_dir / "PROMPT.md").read_text(encoding="utf-8")
    assert "article-morphology" in prompt
    assert "Do not write a slide deck here" in prompt
    assert "every `<math id=... alttext=...>` occurrence" in prompt
    assert "math_analysis.json" in prompt
    assert staged["run_id"] in prompt
    assert staged["cursor_message"] == staged["prompt"]

    runs = morphology.list_morphology_runs(project)
    assert [row["run_id"] for row in runs] == [staged["run_id"]]
    assert runs[0]["status"] == "staged"


def test_stage_requires_a_title_or_url(project) -> None:
    with pytest.raises(ValueError):
        morphology.stage_paper_morphology(project, {"authors": "Nobody"})


def test_run_turns_ready_only_after_both_required_artifacts(project) -> None:
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

    assert morphology.list_morphology_runs(project)[0]["status"] == "staged"

    math_analysis = {
        "version": 1,
        "run_id": staged["run_id"],
        "source_kind": "none",
        "source_math_count": 0,
        "expressions": [],
        "coverage_gaps": ["No saved source was available."],
    }
    (run_dir / "math_analysis.json").write_text(
        json.dumps(math_analysis), encoding="utf-8"
    )

    assert morphology.list_morphology_runs(project)[0]["status"] == "ready"

    loaded = morphology.load_morphology_run(project, staged["run_id"])
    assert loaded["status"] == "ready"
    assert loaded["morphology"]["nodes"][0]["id"] == "n01"
    assert loaded["math_analysis"]["source_math_count"] == 0
    assert loaded["report_markdown"].startswith("# Morphology")
    assert loaded["paper"]["title"] == "Attention Is All You Need"


def test_legacy_run_without_required_artifacts_needs_only_morphology(project) -> None:
    staged = morphology.stage_paper_morphology(project, PAPER)
    run_dir = morphology.morphology_dir(project) / staged["run_id"]
    stored = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    stored.pop("required_artifacts")
    (run_dir / "input.json").write_text(json.dumps(stored), encoding="utf-8")
    (run_dir / "morphology.json").write_text("{}", encoding="utf-8")

    assert morphology.load_morphology_run(project, staged["run_id"])["status"] == "ready"


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


def test_html_article_drops_source_chrome_and_resolves_images(project) -> None:
    staged = morphology.stage_paper_morphology(project, PAPER)
    run_dir = morphology.morphology_dir(project) / staged["run_id"]
    source = """
    <!doctype html>
    <html>
      <head>
        <link rel="stylesheet" href="/static/browse/arxiv-html-papers.css">
        <script>throw new Error("must not run")</script>
      </head>
      <body>
        <header class="arxiv-html-header">arXiv controls</header>
        <nav class="ltx_TOC"><a href="#S1">Long table of contents</a></nav>
        <div class="ltx_page_content">
          <article class="ltx_document">
            <section id="S1">
              <h2>1 Method</h2>
              <p>The exact grounded sentence.</p>
              <math id="S1.E1.m1" alttext="x+1"><mi>x</mi></math>
              <figure><img src="1706.03762v1/figure.png" alt="A figure"></figure>
            </section>
          </article>
        </div>
        <footer>source footer</footer>
      </body>
    </html>
    """
    (run_dir / "article.html").write_text(source, encoding="utf-8")
    (run_dir / "morphology.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "n01",
                        "role": "method_step",
                        "statement": "A method.",
                        "grounding": "quoted",
                        "evidence": [
                            {
                                "quote": "The exact grounded sentence.",
                                "section": "1 Method",
                                "locator": "paragraph 1",
                            }
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )

    article = morphology.build_morphology_article(project, staged["run_id"])
    html = article["html"]
    assert html.lstrip().startswith('<article class="ltx_document">')
    assert "ltx_TOC" not in html
    assert "arxiv-html-header" not in html
    assert "<script" not in html
    assert 'id="S1.E1.m1"' in html
    assert 'src="https://arxiv.org/html/1706.03762v1/figure.png"' in html
    assert article["marked_count"] == 1


def test_ar5iv_image_origin_is_preserved() -> None:
    raw = """
    <meta property="og:url" content="https://ar5iv.labs.arxiv.org/html/2507.07955">
    """
    base = morphology._article_asset_base(raw, "https://arxiv.org/abs/2507.07955")
    html = morphology._resolve_article_images(
        '<img src="/html/2507.07955/assets/main.png">',
        base,
    )
    assert (
        html
        == '<img src="https://ar5iv.labs.arxiv.org/html/2507.07955/assets/main.png">'
    )
