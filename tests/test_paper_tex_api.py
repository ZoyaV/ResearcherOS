"""Tests for editable paper tex API."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from koi.services.paper_generator import TEX_NAME


class PaperTexApiTests(unittest.TestCase):
    def test_put_and_get_tex(self) -> None:
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as tmp:
            slot = Path(tmp) / "emnlp-demo"
            slot.mkdir()
            (slot / "main.tex").write_text("% old\n", encoding="utf-8")

            with patch("api.routers.paper.parse_project"), patch(
                "api.routers.paper.get_paper_slot_dir",
                return_value=slot,
            ):
                put = client.put(
                    "/projects/demo/papers/emnlp-demo/tex",
                    json={"content": "\\documentclass{article}\n\\begin{document}\nHi\n\\end{document}\n"},
                )
                self.assertEqual(put.status_code, 200)
                self.assertTrue(put.json()["ok"])

                get = client.get("/projects/demo/papers/emnlp-demo/tex")
                self.assertEqual(get.status_code, 200)
                self.assertIn("\\documentclass{article}", get.text)

                meta = client.get("/projects/demo/papers/emnlp-demo/tex/meta")
                self.assertEqual(meta.status_code, 200)
                self.assertTrue(meta.json()["tex_exists"])
                self.assertIsInstance(meta.json()["tex_mtime"], float)

            saved = (slot / TEX_NAME).read_text(encoding="utf-8")
            self.assertIn("\\begin{document}", saved)


if __name__ == "__main__":
    unittest.main()
