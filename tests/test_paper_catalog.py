"""Tests for multi-paper catalog under koi-structure/paper/."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from koi.services.paper_catalog import (
    DEFAULT_PAPER_SLUG,
    list_project_papers,
    normalize_paper_slug,
    prepare_paper_slot_dir,
)


class PaperCatalogTests(unittest.TestCase):
    def test_normalize_paper_slug(self) -> None:
        self.assertEqual(normalize_paper_slug(None), DEFAULT_PAPER_SLUG)
        self.assertEqual(normalize_paper_slug("talking-heads-operator"), "talking-heads-operator")
        with self.assertRaises(ValueError):
            normalize_paper_slug("Bad Slug")

    def test_list_legacy_flat_paper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper_root = root / "paper"
            paper_root.mkdir()
            (paper_root / "main.tex").write_text("% legacy", encoding="utf-8")
            (paper_root / "paper.json").write_text(
                json.dumps({"title": "Legacy Paper"}),
                encoding="utf-8",
            )

            with patch(
                "koi.services.paper_catalog.paper_dir",
                return_value=paper_root,
            ):
                papers = list_project_papers("demo")

            self.assertEqual(len(papers), 1)
            self.assertEqual(papers[0]["slug"], DEFAULT_PAPER_SLUG)
            self.assertEqual(papers[0]["title"], "Legacy Paper")
            self.assertTrue(papers[0]["tex_exists"])

    def test_list_subdirectory_papers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper_root = root / "paper"
            slot = paper_root / "talking-heads-operator"
            slot.mkdir(parents=True)
            (slot / "paper.json").write_text(
                json.dumps({"title": "TalkingHeads Operator"}),
                encoding="utf-8",
            )
            (slot / "main.tex").write_text("% slot", encoding="utf-8")

            with patch(
                "koi.services.paper_catalog.paper_dir",
                return_value=paper_root,
            ):
                papers = list_project_papers("talking-heads")

            self.assertEqual(len(papers), 1)
            self.assertEqual(papers[0]["slug"], "talking-heads-operator")
            self.assertEqual(papers[0]["title"], "TalkingHeads Operator")

    def test_status_only_dir_is_not_listed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper_root = Path(tmp) / "paper"
            paper_root.mkdir()
            (paper_root / "status.json").write_text(
                json.dumps({"state": "running", "started_at": "2026-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            with patch("koi.services.paper_catalog.paper_dir", return_value=paper_root):
                papers = list_project_papers("demo")
            self.assertEqual(papers, [])

    def test_prepare_paper_slot_dir_for_named_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper_root = Path(tmp) / "paper"
            with patch(
                "koi.services.paper_catalog.paper_dir",
                return_value=paper_root,
            ):
                slot = prepare_paper_slot_dir("demo", "experiment-a")
            self.assertEqual(slot, paper_root / "experiment-a")
            self.assertTrue(slot.is_dir())


if __name__ == "__main__":
    unittest.main()
