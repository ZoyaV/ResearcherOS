"""Auto-answer UI questions from projects/<id>/research.json when match is confident."""

from __future__ import annotations

import re
from typing import Optional

from koi.services.agent_chat_format import append_sources
from koi.core.models import NodeType
from koi.adapters.repository import load_project

_STOP = {
    "и", "в", "во", "на", "с", "со", "по", "для", "что", "как", "не", "ли", "это",
    "а", "то", "же", "из", "у", "к", "о", "от", "до", "при", "или", "если", "можно",
    "ли", "бы", "еще", "ещё", "все", "всё", "его", "ее", "её", "их", "мы", "вы",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zа-яё0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _score(user_q: str, record: dict) -> float:
    u = _tokenize(user_q)
    scores = [_jaccard(u, _tokenize(record.get("question", "")))]
    blob = " ".join(
        filter(
            None,
            [
                record.get("method_title", ""),
                record.get("narrative", ""),
                record.get("answer", ""),
            ],
        )
    )
    scores.append(_jaccard(u, _tokenize(blob)) * 0.85)
    u_low = user_q.lower()
    method = (record.get("method_title") or "").lower()
    if "sft" in u_low and ("sft" in method or "пример" in method):
        scores.append(0.35)
    if "разнообраз" in u_low and "разнообраз" in blob.lower():
        scores.append(0.25)
    if "diversity" in u_low and "diversity" in method:
        scores.append(0.3)
    return max(scores)


def _card_title(project, board_id: str, card_id: str) -> str | None:
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        return None
    card = next((c for c in board.cards if c.id == card_id), None)
    return card.title if card else None


def _compose_body(matches: list[dict]) -> str:
    paragraphs: list[str] = []
    used_ids: set[str] = set()

    for rec in matches:
        rid = rec.get("id", "")
        if rid in used_ids:
            continue
        used_ids.add(rid)

        narrative = (rec.get("narrative") or "").strip()
        answer = (rec.get("answer") or "").strip()
        certainty = rec.get("certainty", "definite")

        chunk_parts: list[str] = []
        if narrative:
            chunk_parts.append(narrative)
        if answer and answer not in narrative:
            chunk_parts.append(f"По данным эксперимента: {answer}.")

        if not chunk_parts:
            continue

        if certainty == "tentative" and len(matches) == 1:
            chunk_parts.append(
                "Следует учитывать, что этот вывод пока предварительный — "
                "данных может быть недостаточно для окончательного заключения."
            )
        elif certainty == "tentative" and rid != matches[0].get("id"):
            chunk_parts.append("Это уточнение основано на предварительных данных.")

        paragraphs.append(" ".join(chunk_parts))

    if len(paragraphs) > 1:
        lead = paragraphs[0]
        rest = " ".join(paragraphs[1:])
        return f"{lead}\n\nПри этом важный нюанс: {rest}"

    return paragraphs[0] if paragraphs else ""


def _compose_answer(matches: list[dict]) -> str:
    body = _compose_body(matches)
    if not body:
        return ""
    return append_sources(body, matches)


def _load_records(project) -> list[dict]:
    records: list[dict] = []
    for node in project.nodes:
        if node.node_type != NodeType.METHOD or not node.research_questions:
            continue
        board = next((b for b in project.boards if b.owner_node_id == node.id), None)
        board_id = board.id if board else None
        for q in node.research_questions:
            rec = {
                "id": q.id,
                "method_id": node.id,
                "method_title": node.title,
                "question": q.question,
                "narrative": q.narrative,
                "answer": q.answer,
                "certainty": q.certainty.value,
                "importance": q.importance,
                "card_id": q.card_id,
            }
            if q.card_id and board_id:
                title = _card_title(project, board_id, q.card_id)
                if title:
                    rec["experiment_title"] = title
            records.append(rec)
    return records


def try_auto_answer(project_id: str, question: str, *, min_score: float = 0.18) -> Optional[str]:
    project = load_project(project_id, sync_reports=False)
    if project is None:
        return None

    records = _load_records(project)
    if not records:
        return None

    scored = sorted(
        ((_score(question, r), r) for r in records),
        key=lambda x: (-x[0], -x[1].get("importance", 0)),
    )
    best_score, best = scored[0]
    if best_score < min_score:
        return None

    related = [best]
    for score, rec in scored[1:3]:
        if score >= min_score * 0.75 and rec["method_id"] == best["method_id"]:
            related.append(rec)
    return _compose_answer(related)
