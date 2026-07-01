"""Tests for git-based RQ discovery detection."""

from __future__ import annotations

import json

from koi.rq_discoveries import (
    _answer_signature,
    _author_for_card_done,
    _card_column_in_row,
    _patch_moves_card_to_column,
    _patch_moves_card_to_done,
    _questions_from_json,
    author_for_card_column,
    detect_filesystem_rq_discoveries,
    discovery_key,
)


def test_answer_signature_changes_when_narrative_changes() -> None:
    a = {"narrative": "Первый ответ", "answer": "raw"}
    b = {"narrative": "Второй ответ", "answer": "raw"}
    assert _answer_signature(a) != _answer_signature(b)


def test_answer_signature_uses_narrative_over_answer() -> None:
    item = {"narrative": "Текст", "answer": "другое"}
    assert _answer_signature(item) == _answer_signature({"narrative": "Текст"})


def test_questions_from_json_indexed_by_id() -> None:
    payload = json.dumps(
        {
            "version": 1,
            "questions": [
                {"id": "rq-a", "question": "Q?", "answer": "A"},
                {"id": "rq-b", "question": "Q2?"},
            ],
        }
    )
    qs = _questions_from_json(payload)
    assert set(qs) == {"rq-a", "rq-b"}
    assert qs["rq-a"]["question"] == "Q?"


def test_discovery_key_stable() -> None:
    k1 = discovery_key("proj", "rq-1", "abc123")
    k2 = discovery_key("proj", "rq-1", "abc123")
    assert k1 == k2
    assert k1 != discovery_key("proj", "rq-1", "other")


def test_card_column_in_row_done() -> None:
    row = "|  |  | Bench <!-- id:zs-bench desc:Table 1 --> |"
    assert _card_column_in_row(row, "zs-bench") == "done"
    assert _card_column_in_row(row, "other") is None


def test_patch_moves_card_to_done() -> None:
    patch = """@@ -1,3 +1,3 @@
-| Bench <!-- id:zs-bench desc:old --> |  |  |
+|  |  | Bench <!-- id:zs-bench desc:new --> |"""
    assert _patch_moves_card_to_done(patch, "zs-bench") is True
    assert _patch_moves_card_to_done(patch, "missing") is False


def test_patch_moves_card_to_running() -> None:
    patch = """@@ -1,3 +1,3 @@
-| Task <!-- id:card-1 desc:old --> |  |  |
+|  | Task <!-- id:card-1 desc:new --> |  |"""
    assert _patch_moves_card_to_column(patch, "card-1", "running") is True
    assert _patch_moves_card_to_column(patch, "card-1", "done") is False


def test_author_for_card_done_from_git_history() -> None:
    author = _author_for_card_done(
        "ai-agents-embodied",
        "zs-bench",
        "e1680b6^",
        "e1680b6",
    )
    assert author == "zoya"


def test_filesystem_detects_new_question_with_answer(tmp_path, monkeypatch) -> None:
    from koi.adapters import project_mount

    koi = tmp_path / "koi-structure"
    koi.mkdir()
    research = koi / "research.json"
    research.write_text(
        json.dumps(
            {
                "version": 1,
                "questions": [
                    {
                        "id": "rq-new",
                        "question": "Новый вопрос?",
                        "narrative": "Готовый ответ",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "project.md").write_text("---\nid: demo\n---\n", encoding="utf-8")

    mount = project_mount.ProjectMount(
        project_id="demo",
        repo_root=tmp_path,
        koi_root=koi,
        code_root=tmp_path,
        programs=(),
    )
    monkeypatch.setattr(project_mount, "list_mounts", lambda: [mount])
    monkeypatch.setattr(
        "koi.adapters.paths.research_json",
        lambda project_id: research,
    )

    items, _sigs = detect_filesystem_rq_discoveries({}, initialized=True)
    assert len(items) == 1
    assert items[0]["question_id"] == "rq-new"
    assert items[0]["answer"] == "Готовый ответ"
