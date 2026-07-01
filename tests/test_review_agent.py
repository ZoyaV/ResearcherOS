import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from koi.workspace import get_workspace

from koi.review_agent import (
    PaperAnswerArtifact,
    PaperAnswerCluster,
    PaperSummary,
    _assignment_rationale,
    _extract_json_object,
    _normalize_llm_evidence,
    _paper_answer_artifact_from_dict,
    _parse_paper_answer_clusters,
    _write_universal_agent_bundle,
    build_paper_answer_cluster_report,
    classify_papers_to_clusters,
    extract_arxiv_html_text,
    extract_arxiv_id,
    infer_year_from_arxiv_id,
    parse_review_report_markdown,
    propose_clusters,
)


class ReviewAgentTests(unittest.TestCase):
    @staticmethod
    def _summary(
        *,
        strategy_key: str,
        strategy_label: str,
        query_answer: str,
        signature_terms: tuple[str, ...],
        evidence: tuple[str, ...] = ("Evidence sentence one.", "Evidence sentence two."),
    ) -> PaperSummary:
        return PaperSummary(
            core_idea=query_answer,
            representation_of_dynamics=query_answer,
            query_answer=query_answer,
            answer_strategy_key=strategy_key,
            answer_strategy_label=strategy_label,
            answer_evidence=evidence,
            evidence=" ".join(evidence),
            usefulness="Useful for the research question.",
            limitations="Uses full paper text.",
            signature_terms=signature_terms,
            citation_sentences=evidence,
        )

    def test_parse_review_report_markdown(self) -> None:
        text = """# Test Paper

- Query: How can scene dynamics be represented?
- Score: 12.3
- ArXiv: http://arxiv.org/abs/2401.12345
- Matched terms: scene, dynamics, graph

## Abstract

We propose a dynamic scene graph with temporal edges for robot planning.

## Screening Notes

- Relevance:
"""
        paper = parse_review_report_markdown(text, "reports/test.md")
        self.assertIsNotNone(paper)
        assert paper is not None
        self.assertEqual(paper.title, "Test Paper")
        self.assertEqual(paper.query, "How can scene dynamics be represented?")
        self.assertEqual(paper.abstract, "We propose a dynamic scene graph with temporal edges for robot planning.")
        self.assertEqual(paper.matched_terms, ("scene", "dynamics", "graph"))

    def test_extract_arxiv_id_strips_version(self) -> None:
        self.assertEqual(extract_arxiv_id("http://arxiv.org/abs/2401.12345v2"), "2401.12345")

    def test_infer_year_from_arxiv_id(self) -> None:
        self.assertEqual(infer_year_from_arxiv_id("2401.12345"), 2024)
        self.assertIsNone(infer_year_from_arxiv_id("hep-th/9901001"))

    def test_propose_clusters_groups_similar_summaries(self) -> None:
        paper1 = parse_review_report_markdown(
            """# ForecastSG

- Query: How can scene dynamics be represented in scene graphs?
- Score: 18.4
- ArXiv: http://arxiv.org/abs/2506.01487

## Abstract

This paper forecasts future scene graph states with a sequential dynamics model and evaluates on a forecasting benchmark.
""",
            "reports/forecast.md",
        )
        paper2 = parse_review_report_markdown(
            """# FutureGraph

- Query: How can scene dynamics be represented in scene graphs?
- Score: 17.1
- ArXiv: http://arxiv.org/abs/2506.11111

## Abstract

We predict future graph states from temporal scene observations with a recurrent sequence model.
""",
            "reports/future.md",
        )
        assert paper1 is not None and paper2 is not None
        summaries = {
            paper1.title: self._summary(
                strategy_key="state_forecasting",
                strategy_label="State Forecasting",
                query_answer="Dynamics are represented by forecasting future scene graph states.",
                signature_terms=("forecasting", "future states", "scene graph"),
            ),
            paper2.title: self._summary(
                strategy_key="state_forecasting",
                strategy_label="State Forecasting",
                query_answer="Dynamics are represented by predicting future graph states from temporal observations.",
                signature_terms=("prediction", "temporal observations", "future states"),
            ),
        }
        clusters = propose_clusters(paper1.query, [paper1, paper2], summaries)
        self.assertEqual(len(clusters), 1)
        self.assertTrue(clusters[0].label)
        self.assertTrue(clusters[0].answer_hint)
        self.assertGreaterEqual(len(clusters[0].signature_terms), 2)
        self.assertEqual(clusters[0].strategy_key, "state_forecasting")

    def test_propose_clusters_splits_distinct_summary_families(self) -> None:
        papers = [
            parse_review_report_markdown(
                f"""# LatentForecast{index}

- Query: How can scene dynamics be represented in scene graphs?
- Score: 18.{index}
- ArXiv: http://arxiv.org/abs/2506.0148{index}

## Abstract

This paper forecasts future scene graph states with latent dynamics and a generative decoder.
""",
                f"reports/latent_{index}.md",
            )
            for index in range(1, 4)
        ]
        papers.extend(
            [
                parse_review_report_markdown(
                    f"""# PlanningGraph{index}

- Query: How can scene dynamics be represented in scene graphs?
- Score: 17.{index}
- ArXiv: http://arxiv.org/abs/2506.1111{index}

## Abstract

We use scene graphs for robot planning, navigation, and control under changing world states.
""",
                    f"reports/planning_{index}.md",
                )
                for index in range(1, 4)
            ]
        )
        assert all(paper is not None for paper in papers)
        typed_papers = [paper for paper in papers if paper is not None]
        summaries = {}
        for paper in typed_papers[:3]:
            summaries[paper.title] = self._summary(
                strategy_key="state_forecasting",
                strategy_label="State Forecasting",
                query_answer="Dynamics are represented as predicted future scene graph states.",
                signature_terms=("forecasting", "future states", "decoder"),
            )
        for paper in typed_papers[3:]:
            summaries[paper.title] = self._summary(
                strategy_key="planning_semantic_map",
                strategy_label="Planning And Semantic World Models",
                query_answer="Dynamics are represented in the service of planning and control under changing world states.",
                signature_terms=("planning", "control", "changing world"),
            )
        clusters = propose_clusters(typed_papers[0].query, typed_papers, summaries)
        self.assertEqual(len(clusters), 2)

    def test_propose_clusters_keeps_distinct_strategies_even_for_small_groups(self) -> None:
        papers = [
            parse_review_report_markdown(
                f"""# ForecastGraph{index}

- Query: How can scene dynamics be represented in scene graphs?
- Score: 18.{index}
- ArXiv: http://arxiv.org/abs/2506.0148{index}

## Abstract

This paper forecasts future scene graph states with sequential latent updates and a temporal benchmark.
""",
                f"reports/forecast_{index}.md",
            )
            for index in range(1, 3)
        ]
        papers.extend(
            [
                parse_review_report_markdown(
                    f"""# PlanningGraph{index}

- Query: How can scene dynamics be represented in scene graphs?
- Score: 17.{index}
- ArXiv: http://arxiv.org/abs/2506.1111{index}

## Abstract

We use scene graphs for robot planning, navigation, and control under changing world states.
""",
                    f"reports/planning_{index}.md",
                )
                for index in range(1, 3)
            ]
        )
        assert all(paper is not None for paper in papers)
        typed_papers = [paper for paper in papers if paper is not None]
        summaries = {}
        for paper in typed_papers[:2]:
            summaries[paper.title] = self._summary(
                strategy_key="state_forecasting",
                strategy_label="State Forecasting",
                query_answer="Dynamics are represented by forecasting future graph states.",
                signature_terms=("forecasting", "future graph", "temporal benchmark"),
            )
        for paper in typed_papers[2:]:
            summaries[paper.title] = self._summary(
                strategy_key="planning_semantic_map",
                strategy_label="Planning And Semantic World Models",
                query_answer="Dynamics are represented to support planning and navigation under changing states.",
                signature_terms=("planning", "navigation", "changing states"),
            )
        clusters = propose_clusters(typed_papers[0].query, typed_papers, summaries)
        self.assertEqual(len(clusters), 2)
        self.assertGreaterEqual(len(clusters[0].signature_terms), 2)

    def test_classify_papers_to_clusters_uses_proposed_clusters(self) -> None:
        paper = parse_review_report_markdown(
            """# MotionGraph

- Query: How can scene dynamics be represented in scene graphs?
- Score: 19.0
- ArXiv: http://arxiv.org/abs/2501.00001

## Abstract

We encode temporal relations and motion trajectories directly inside a 4D scene graph.
""",
            "reports/motion.md",
        )
        assert paper is not None
        summaries = {
            paper.title: self._summary(
                strategy_key="temporal_layer",
                strategy_label="Temporal Layers And Motion Fields",
                query_answer="Dynamics are represented by adding a dedicated temporal layer into the scene graph.",
                signature_terms=("temporal layer", "motion trajectories", "4d scene graph"),
            )
        }
        clusters = propose_clusters(paper.query, [paper], summaries)
        assignments = classify_papers_to_clusters([paper], summaries, clusters)
        self.assertEqual(assignments[paper.title].key, clusters[0].key)

    def test_assignment_rationale_uses_multiple_sentences_with_citations(self) -> None:
        paper = parse_review_report_markdown(
            """# PlanningGraph

- Query: How can scene dynamics be represented in scene graphs?
- Score: 17.1
- ArXiv: http://arxiv.org/abs/2506.11111

## Abstract

We use scene graphs for robot planning in changing environments. The paper represents scene changes as evolving object relations over time. Experiments show improved navigation decisions in dynamic settings.
""",
            "reports/planning.md",
        )
        assert paper is not None
        summaries = {
            paper.title: self._summary(
                strategy_key="planning_semantic_map",
                strategy_label="Planning And Semantic World Models",
                query_answer="Dynamics are represented as evolving object relations used for planning decisions.",
                signature_terms=("planning", "relations", "dynamic settings"),
                evidence=(
                    "The paper uses scene graphs for robot planning in changing environments.",
                    "It represents scene changes as evolving object relations over time.",
                ),
            )
        }
        clusters = propose_clusters(paper.query, [paper], summaries)
        rationale = _assignment_rationale(paper, summaries[paper.title], clusters[0])
        self.assertGreaterEqual(rationale.count("."), 2)
        self.assertIn('"', rationale)

    def test_extract_json_object_parses_fenced_json(self) -> None:
        payload = _extract_json_object(
            """```json
{
  "short_answer": "Direct answer.",
  "detailed_answer": "Detailed answer.",
  "evidence": ["Snippet one.", "Snippet two."],
  "limitations": "Used full text."
}
```"""
        )
        self.assertIsInstance(payload, dict)
        assert payload is not None
        self.assertEqual(payload["short_answer"], "Direct answer.")

    def test_parse_paper_answer_clusters_parses_valid_payload(self) -> None:
        payload = {
            "clusters": [
                {
                    "label": "Temporal Layers",
                    "answer": "These papers represent dynamics by adding explicit temporal structure to the graph.",
                    "rationale": "They should be grouped because they treat time as part of the graph representation itself. This differs from clusters that mainly use the graph for downstream planning or forecasting.",
                    "distinguishing_features": "The graph directly stores temporal flow, trajectories, or motion-aware state.",
                    "signature_terms": ["temporal flow", "4d scene graph", "motion field"],
                    "paper_titles": ["Paper A", "Paper B"],
                }
            ]
        }
        clusters = _parse_paper_answer_clusters(
            payload,
            valid_titles=("Paper A", "Paper B"),
        )
        self.assertIsNotNone(clusters)
        assert clusters is not None
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].label, "Temporal Layers")
        self.assertEqual(clusters[0].paper_titles, ("Paper A", "Paper B"))

    def test_paper_answer_artifact_from_dict_parses_saved_answer(self) -> None:
        artifact = _paper_answer_artifact_from_dict(
            {
                "rank": 1,
                "title": "Paper A",
                "arxiv_url": "http://arxiv.org/abs/2401.12345",
                "arxiv_id": "2401.12345",
                "year": 2024,
                "source_report": "selected_results",
                "answer_path": "01_Paper_A.md",
                "html_path": "htmls/2401.12345.html",
                "pdf_path": "pdfs/2401.12345.pdf",
                "text_path": "texts/2401.12345.txt",
                "extracted_text_chars": 1000,
                "used_full_text": True,
                "answer_backend": "codex",
                "answer_source": "llm_agent",
                "short_answer": "Short answer.",
                "comprehensive_answer": "Detailed answer.",
                "evidence": ["Snippet one.", "Snippet two."],
                "limitations": "Used full text.",
            }
        )
        self.assertIsNotNone(artifact)
        assert artifact is not None
        self.assertEqual(artifact.title, "Paper A")
        self.assertEqual(artifact.answer_backend, "codex")
        self.assertEqual(artifact.evidence, ("Snippet one.", "Snippet two."))

    def test_build_paper_answer_cluster_report_includes_rationale(self) -> None:
        artifacts = [
            PaperAnswerArtifact(
                rank=1,
                title="Paper A",
                arxiv_url="http://arxiv.org/abs/2401.12345",
                arxiv_id="2401.12345",
                year=2024,
                source_report="reports/a.md",
                answer_path="01_Paper_A.md",
                html_path=None,
                pdf_path=None,
                text_path=None,
                extracted_text_chars=1000,
                used_full_text=True,
                answer_backend="codex",
                answer_source="llm_agent",
                short_answer="Paper A uses a temporal layer.",
                comprehensive_answer="Detailed answer A.",
                evidence=("Temporal flow is stored in the graph.",),
                limitations="Uses full text.",
                cluster_key="temporal-layers",
                cluster_label="Temporal Layers",
                cluster_rationale="These papers belong together because they encode dynamics directly in the graph structure.",
            )
        ]
        clusters = [
            PaperAnswerCluster(
                key="temporal-layers",
                label="Temporal Layers",
                answer="Dynamics are represented by adding explicit temporal structure.",
                rationale="This cluster should exist because the papers encode time inside the graph itself rather than only using the graph downstream.",
                distinguishing_features="The representation stores motion-aware graph state.",
                signature_terms=("temporal flow", "4d scene graph"),
                paper_titles=("Paper A",),
            )
        ]
        report = build_paper_answer_cluster_report(
            "How can scene dynamics be represented in scene graphs?",
            artifacts,
            clusters,
            cluster_backend="codex",
        )
        self.assertIn("Why this cluster should exist", report)
        self.assertIn("Temporal Layers", report)
        self.assertIn("Cluster backend: codex", report)

    def test_normalize_llm_evidence_filters_non_strings(self) -> None:
        evidence = _normalize_llm_evidence(
            [" First snippet. ", None, "Second snippet.", 42, "First snippet."],
            limit=5,
        )
        self.assertEqual(evidence, ("First snippet.", "Second snippet."))

    def test_extract_arxiv_html_text_discards_markup(self) -> None:
        with TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "paper.html"
            html_path.write_text(
                """<html><body><article><h1>Title</h1><p>First paragraph.</p><script>ignored()</script><p>Second paragraph.</p></article></body></html>""",
                encoding="utf-8",
            )
            text = extract_arxiv_html_text(html_path)
            self.assertIn("Title", text)
            self.assertIn("First paragraph.", text)
            self.assertIn("Second paragraph.", text)
            self.assertNotIn("ignored()", text)

    def test_universal_agent_bundle_is_written(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "demo_repo"
            koi = repo / "koi-structure"
            koi.mkdir(parents=True)
            (koi / "project.md").write_text(
                "---\nid: demo-project\ntitle: Demo\n---\n\n# problem: p\n\nDemo\n",
                encoding="utf-8",
            )
            review_dir = koi / "paper_reviews" / "test-review"
            review_dir.mkdir(parents=True)
            from koi.adapters import project_mount as pm
            from koi.adapters.workspace import reset_workspace_cache

            old_engine = pm.ENGINE_ROOT
            pm.ENGINE_ROOT = root / "ReseachOS"
            pm.ENGINE_ROOT.mkdir()
            import os

            os.environ["KOI_SCAN_ROOTS"] = str(root)
            reset_workspace_cache()
            pm.rescan_projects()
            try:
                manifest = {
                    "cluster_report": "cluster_directions.md",
                    "papers": [
                        {
                            "summary_path": "01_Test_Paper.md",
                            "text_path": "texts/2401.12345.txt",
                            "html_path": "htmls/2401.12345.html",
                            "pdf_path": "pdfs/2401.12345.pdf",
                        }
                    ],
                }
                _write_universal_agent_bundle(
                    review_dir,
                    project_id="demo-project",
                    bundle_name="demo-bundle",
                    query="How is dynamics represented?",
                    manifest=manifest,
                )
                bundle = koi / "agent_bundles" / "paper_review" / "demo-bundle"
                self.assertTrue((bundle / "manifest.json").exists())
                self.assertTrue((bundle / "UNIVERSAL_PROMPT.md").exists())
                self.assertTrue((bundle / "CURSOR.md").exists())
                self.assertTrue((bundle / "CLAUDE.md").exists())
                self.assertTrue((bundle / "CODEX.md").exists())
                self.assertIn(
                    "Universal Paper Review Agent",
                    (bundle / "UNIVERSAL_PROMPT.md").read_text(),
                )
                self.assertIn("paper_html_caches", (bundle / "manifest.json").read_text())
            finally:
                pm.ENGINE_ROOT = old_engine
                os.environ.pop("KOI_SCAN_ROOTS", None)
                reset_workspace_cache()


if __name__ == "__main__":
    unittest.main()
