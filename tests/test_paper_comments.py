"""Tests for paper review comments sidecar."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from koi.paper.comments import (
    add_reply,
    apply_comment_merge,
    compute_content_hash,
    create_comment,
    delete_comment,
    load_comments,
    merge_comment_stores,
    set_comment_resolved,
)


class PaperCommentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.slot = Path(self.tmp.name)
        (self.slot / "main.tex").write_text("line one\nline two\nline three\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_and_load_comment(self) -> None:
        comment = create_comment(
            self.slot,
            line_start=2,
            line_end=2,
            body="Clarify notation here",
            author="zoya",
        )
        self.assertTrue(comment["id"].startswith("c_"))
        self.assertEqual(comment["anchor"]["line_start"], 2)
        self.assertTrue(comment["anchor"]["content_hash"].startswith("sha256:"))

        data = load_comments(self.slot)
        self.assertEqual(len(data["comments"]), 1)
        path = self.slot / "comments.json"
        self.assertTrue(path.is_file())
        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["version"], 1)

    def test_reply_resolve_delete(self) -> None:
        comment = create_comment(
            self.slot,
            line_start=1,
            line_end=1,
            body="First note",
        )
        message = add_reply(self.slot, comment["id"], body="Follow-up", author="agent")
        self.assertTrue(message["id"].startswith("m_"))

        updated = set_comment_resolved(self.slot, comment["id"], resolved=True)
        self.assertTrue(updated["resolved"])

        delete_comment(self.slot, comment["id"])
        self.assertEqual(load_comments(self.slot)["comments"], [])

    def test_compute_content_hash(self) -> None:
        tex = (self.slot / "main.tex").read_text(encoding="utf-8")
        h1 = compute_content_hash(tex, 1, 2)
        h2 = compute_content_hash(tex, 1, 2)
        h3 = compute_content_hash(tex, 3, 3)
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_partial_anchor_text(self) -> None:
        tex = (self.slot / "main.tex").read_text(encoding="utf-8")
        partial = compute_content_hash(tex, 2, 2, 5, 9)
        full = compute_content_hash(tex, 2, 2)
        self.assertNotEqual(partial, full)
        comment = create_comment(
            self.slot,
            line_start=2,
            line_end=2,
            char_start=5,
            char_end=9,
            selected_text="two",
            body="narrow note",
        )
        self.assertEqual(comment["anchor"]["selected_text"], "two")

    def test_merge_unions_threads_and_honours_deletes(self) -> None:
        first = create_comment(self.slot, line_start=1, line_end=1, body="A")
        add_reply(self.slot, first["id"], body="A2", author="zoya")
        local = load_comments(self.slot)["comments"]
        incoming = [
            {
                "id": first["id"],
                "resolved": True,
                "thread": [{"id": "m_remote", "author": "peer", "body": "B"}],
            },
            {
                "id": "c_other",
                "resolved": False,
                "thread": [{"id": "m_1", "author": "peer", "body": "new"}],
            },
        ]
        merged = merge_comment_stores(local, incoming, deleted_ids=[])
        by_id = {item["id"]: item for item in merged}
        self.assertIn("c_other", by_id)
        thread_ids = {item["id"] for item in by_id[first["id"]]["thread"]}
        self.assertIn("m_remote", thread_ids)
        self.assertTrue(any(item["body"] == "A2" for item in by_id[first["id"]]["thread"]))
        self.assertTrue(by_id[first["id"]]["resolved"])

        stored = apply_comment_merge(self.slot, incoming, [first["id"]])
        ids = {item["id"] for item in stored["comments"]}
        self.assertNotIn(first["id"], ids)
        self.assertIn("c_other", ids)


if __name__ == "__main__":
    unittest.main()
