"""Research questions stored in projects/<id>/research.json (not project.md)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from koi.core.models import (
    MethodResearchQuestion,
    NodeType,
    Project,
    ResearchQuestionCertainty,
)
from koi.adapters.paths import research_json

RESEARCH_VERSION = 1


def research_path(project_id: str) -> Path:
    return research_json(project_id)


def _question_to_record(method_id: str, q: MethodResearchQuestion) -> dict:
    record: dict = {
        "id": q.id,
        "method_id": method_id,
        "question": q.question,
        "certainty": q.certainty.value,
        "importance": q.importance,
    }
    if q.answer:
        record["answer"] = q.answer
    if q.narrative:
        record["narrative"] = q.narrative
    if q.card_id:
        record["card_id"] = q.card_id
    return record


def _record_to_question(item: dict) -> Optional[MethodResearchQuestion]:
    if not isinstance(item, dict):
        return None
    question = str(item.get("question") or "").strip()
    if not question:
        return None
    certainty_raw = str(item.get("certainty", "definite")).lower()
    try:
        certainty = ResearchQuestionCertainty(certainty_raw)
    except ValueError:
        certainty = ResearchQuestionCertainty.DEFINITE
    importance_raw = item.get("importance", 3)
    try:
        importance = max(1, min(5, int(importance_raw)))
    except (TypeError, ValueError):
        importance = 3
    card_id_raw = item.get("card_id")
    card_id = str(card_id_raw).strip() if card_id_raw else None
    return MethodResearchQuestion(
        id=str(item.get("id") or f"rq-{question[:8]}"),
        question=question,
        answer=str(item.get("answer") or "").strip(),
        narrative=str(item.get("narrative") or "").strip(),
        certainty=certainty,
        importance=importance,
        card_id=card_id or None,
    )


def questions_from_project(project: Project) -> list[dict]:
    records: list[dict] = []
    for node in project.nodes:
        if node.node_type != NodeType.METHOD or not node.research_questions:
            continue
        for q in node.research_questions:
            records.append(_question_to_record(node.id, q))
    return records


def save_research(project: Project) -> Path:
    path = research_path(project.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": RESEARCH_VERSION,
        "questions": questions_from_project(project),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_research_questions(project_id: str) -> dict[str, list[MethodResearchQuestion]]:
    path = research_path(project_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    raw = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return {}
    by_method: dict[str, list[MethodResearchQuestion]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        method_id = str(item.get("method_id") or "").strip()
        if not method_id:
            continue
        q = _record_to_question(item)
        if q is None:
            continue
        by_method.setdefault(method_id, []).append(q)
    return by_method


def apply_research_to_project(project: Project, by_method: dict[str, list[MethodResearchQuestion]]) -> None:
    method_ids = {n.id for n in project.nodes if n.node_type == NodeType.METHOD}
    for node in project.nodes:
        if node.node_type != NodeType.METHOD:
            node.research_questions = []
            continue
        node.research_questions = by_method.get(node.id, [])


def md_has_legacy_question_blocks(text: str) -> bool:
    return "<!-- koi:method-questions -->" in text.lower()


def merge_research_from_md(project: Project) -> bool:
    """If research.json is missing, persist questions still embedded in project.md."""
    if research_path(project.id).exists():
        return False
    has_md_questions = any(
        n.research_questions for n in project.nodes if n.node_type == NodeType.METHOD
    )
    if not has_md_questions:
        return False
    save_research(project)
    return True
