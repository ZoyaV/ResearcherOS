import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from koi.literature import (
    LIBRARY_FIELDNAMES,
    discover_library_with_agent,
    reset_library_cache,
    search_library,
)


class LiteratureBootstrapTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_library_cache()

    def test_discover_library_with_agent_writes_csv_and_supports_search(self) -> None:
        response = """
        {
          "query": "dynamic scene graphs",
          "papers": [
            {
              "title": "Dynamic Scene Graph Networks",
              "arxiv_url": "https://arxiv.org/pdf/2401.12345v2",
              "authors": ["Alice Example", "Bob Example"],
              "abstract": "We model changing scenes with dynamic scene graphs for embodied reasoning."
            },
            {
              "title": "Temporal Graph World Models",
              "arxiv_url": "https://arxiv.org/abs/2402.54321",
              "authors": "Carol Example, Dan Example",
              "abstract": "A temporal graph representation captures state changes over time."
            }
          ],
          "notes": "Collected from scholar-style search."
        }
        """
        with TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "library.csv"
            with patch("koi.literature.run_agent", return_value=(response, "mock-agent")):
                result = discover_library_with_agent(
                    "dynamic scene graphs", limit=2, destination=destination
                )

            self.assertEqual(result["count"], 2)
            self.assertEqual(result["backend"], "mock-agent")
            self.assertTrue(destination.exists())

            with destination.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(tuple(rows[0].keys()), LIBRARY_FIELDNAMES)
            self.assertEqual(rows[0]["arxiv_url"], "https://arxiv.org/abs/2401.12345")
            self.assertEqual(rows[0]["authors"], "Alice Example, Bob Example")

            with patch("koi.literature.LIBRARY_CSV_CANDIDATES", (destination,)):
                reset_library_cache()
                ranked = search_library("dynamic embodied scene graph reasoning", limit=5)
            self.assertGreaterEqual(len(ranked), 1)
            self.assertEqual(ranked[0]["title"], "Dynamic Scene Graph Networks")

    def test_library_discover_endpoint_runs_explicit_refresh(self) -> None:
        client = TestClient(app)
        with patch(
            "api.main.discover_library_with_agent",
            return_value={
                "ok": True,
                "query": "scene graph dynamics",
                "count": 3,
                "csv_path": "library/library.csv",
                "fields": list(LIBRARY_FIELDNAMES),
                "required_fields": ["no", "arxiv_url", "title", "authors", "abstract"],
                "backend": "mock-agent",
                "notes": "",
                "papers": [],
            },
        ):
            response = client.post(
                "/library/discover",
                json={"query": "scene graph dynamics", "limit": 3},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["backend"], "mock-agent")
        self.assertEqual(payload["csv_path"], "library/library.csv")

    def test_library_search_endpoint_requires_existing_library(self) -> None:
        client = TestClient(app)
        with patch("api.main.resolve_library_csv", side_effect=FileNotFoundError("missing")):
            response = client.post(
                "/library/search",
                json={"query": "scene graph dynamics", "limit": 3},
            )

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertIn("separate library refresh button", payload["detail"])

    def test_search_arxiv_internet_parses_atom_feed(self) -> None:
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title> Dynamic Scene Graph Networks </title>
            <id>https://arxiv.org/abs/2401.12345v1</id>
            <summary>We model changing scenes with dynamic scene graphs.</summary>
            <author><name>Alice Example</name></author>
          </entry>
        </feed>"""
        with patch("koi.literature.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = xml
            from koi.literature import search_arxiv_internet

            results = search_arxiv_internet("dynamic scene graphs", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Dynamic Scene Graph Networks")
        self.assertEqual(results[0]["arxiv_url"], "https://arxiv.org/abs/2401.12345")

    def test_translate_to_english_passthrough_for_latin_text(self) -> None:
        from koi.literature import translate_to_english

        translated, backend = translate_to_english("scene graph planning")
        self.assertEqual(translated, "scene graph planning")
        self.assertEqual(backend, "passthrough")

    def test_library_search_internet_endpoint(self) -> None:
        client = TestClient(app)
        with patch(
            "api.routers.library.search_arxiv_internet",
            return_value=[
                {
                    "title": "Scene Graph Paper",
                    "arxiv_url": "https://arxiv.org/abs/2401.12345",
                    "authors": "A B",
                    "abstract": "Abstract text",
                    "abstract_preview": "Abstract text",
                    "score": 1.0,
                    "matched_terms": ["scene"],
                }
            ],
        ):
            response = client.post(
                "/library/search-internet",
                json={"query": "scene graph", "limit": 3},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["source"]["method"], "arxiv_api")

    def test_translate_endpoint_uses_fallback_without_agent(self) -> None:
        client = TestClient(app)
        with patch(
            "api.routers.library.translate_to_english",
            return_value=("scene graph", "passthrough"),
        ):
            response = client.post(
                "/agent/translate-to-english",
                json={"text": "scene graph"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["backend"], "passthrough")

    def test_related_works_endpoint_returns_generated_markdown(self) -> None:
        client = TestClient(app)
        with patch(
            "api.routers.review.submit_related_work_request",
            return_value={
                "project_id": "ai-agents-embodied",
                "question": "How do embodied agents improve performance?",
                "problem": "Low performance of LLM agents in embodied settings.",
                "cluster_keys": ["memory", "world-models"],
                "cluster_labels": ["Memory", "World Models"],
                "paper_count": 6,
                "backend": "mock-agent",
                "markdown": "## Related Works\n\nPrior work...",
                "status": "answered",
            },
        ):
            response = client.post(
                "/projects/ai-agents-embodied/paper-question-agent/related-works",
                json={
                    "problem": "Low performance of LLM agents in embodied settings.",
                    "cluster_keys": ["memory", "world-models"],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["backend"], "mock-agent")
        self.assertEqual(payload["paper_count"], 6)
        self.assertTrue(payload["markdown"].startswith("## Related Works"))


if __name__ == "__main__":
    unittest.main()
