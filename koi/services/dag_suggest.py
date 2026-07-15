"""Suggest prerequisite edges between kanban cards on a method board."""

from __future__ import annotations

import re
from typing import Any, Optional

from koi.adapters.card_reports import read_report
from koi.core.models import ExperimentCard, KanbanBoard, Node, Project

DONE_COLUMNS = frozenset({"done", "successful"})


def normalize_dependency_ids(
    raw: list[str] | None,
    valid_ids: set[str],
    self_id: str = "",
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        dep = str(item or "").strip()
        if not dep or dep == self_id or dep not in valid_ids or dep in seen:
            continue
        seen.add(dep)
        out.append(dep)
    return out


def normalize_depends_on_list(
    deps: list[str] | None,
    board: KanbanBoard,
    *,
    self_id: str = "",
) -> list[str]:
    valid = {c.id for c in board.cards}
    normalized = normalize_dependency_ids(deps, valid, self_id)
    if self_id and would_create_cycle(board.cards, self_id, normalized):
        return []
    return normalized


def normalize_card_depends_on(
    card: ExperimentCard,
    board: KanbanBoard,
    *,
    allow_cycles: bool = False,
) -> list[str]:
    """Keep only valid same-board prerequisite ids."""
    valid = {c.id for c in board.cards}
    deps = normalize_dependency_ids(card.depends_on, valid, card.id)
    if allow_cycles:
        return deps
    if would_create_cycle(board.cards, card.id, deps):
        return list(card.depends_on or [])
    return deps


def would_create_cycle(
    cards: list[ExperimentCard],
    card_id: str,
    new_deps: list[str],
) -> bool:
    graph = {c.id: list(c.depends_on or []) for c in cards}
    graph[card_id] = list(new_deps)

    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in graph.get(node, []):
            if dfs(dep):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    for cid in graph:
        if dfs(cid):
            return True
    return False


# Compatibility aliases for callers using the original private names.
_normalize_dep_ids = normalize_dependency_ids
_would_create_cycle = would_create_cycle


def _card_text(card: ExperimentCard, report: str = "") -> str:
    parts = [card.title, card.description or "", report or ""]
    return " ".join(p.strip() for p in parts if p.strip()).lower()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.split(r"[^\wа-яё]+", text.lower()) if len(t) >= 4}


def _overlap_score(a: str, b: str) -> float:
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return inter / max(1, min(len(ta), len(tb)))


def _method_for_board(project: Project, board: KanbanBoard) -> Optional[Node]:
    return next((n for n in project.nodes if n.id == board.owner_node_id), None)


def suggest_board_dag(
    project: Project,
    board: KanbanBoard,
    *,
    include_reports: bool = True,
) -> list[dict[str, Any]]:
    """Return suggested prerequisite edges (from → to means *to* depends on *from*)."""
    cards = list(board.cards or [])
    if len(cards) < 2:
        return []

    card_by_id = {c.id: c for c in cards}
    reports: dict[str, str] = {}
    if include_reports:
        for card in cards:
            try:
                payload = read_report(project, board.id, card.id, card.title)
                reports[card.id] = str(payload.get("content") or "")
            except (OSError, KeyError, TypeError):
                reports[card.id] = ""

    method = _method_for_board(project, board)
    rq_by_card: dict[str, list[str]] = {}
    if method:
        for q in method.research_questions:
            if q.card_id:
                rq_by_card.setdefault(q.card_id, []).append(
                    " ".join(
                        p
                        for p in [q.question, q.narrative, q.answer]
                        if str(p or "").strip()
                    )
                )

    suggestions: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()

    def add(from_id: str, to_id: str, reason: str, confidence: float) -> None:
        if from_id == to_id:
            return
        key = (from_id, to_id)
        if key in seen_edges:
            return
        if to_id not in card_by_id or from_id not in card_by_id:
            return
        if from_id in (card_by_id[to_id].depends_on or []):
            return
        seen_edges.add(key)
        suggestions.append(
            {
                "from_card_id": from_id,
                "to_card_id": to_id,
                "from_title": card_by_id[from_id].title,
                "to_title": card_by_id[to_id].title,
                "reason": reason,
                "confidence": round(confidence, 2),
            }
        )

    done_cards = [c for c in cards if c.column_id in DONE_COLUMNS]
    open_cards = [c for c in cards if c.column_id not in DONE_COLUMNS]

    for open_card in open_cards:
        open_text = _card_text(open_card, reports.get(open_card.id, ""))
        for done_card in done_cards:
            done_text = _card_text(done_card, reports.get(done_card.id, ""))
            score = _overlap_score(open_text, done_text)
            if score >= 0.25:
                add(
                    done_card.id,
                    open_card.id,
                    "Backlog-карточка пересекается по теме с завершённым экспериментом",
                    min(0.95, 0.45 + score),
                )
            for rq_text in rq_by_card.get(done_card.id, []):
                rq_score = _overlap_score(open_text, rq_text)
                if rq_score >= 0.2:
                    add(
                        done_card.id,
                        open_card.id,
                        "Карточка продолжает вопрос из вывода завершённого эксперимента",
                        min(0.98, 0.5 + rq_score),
                    )

    for card in cards:
        text = _card_text(card, reports.get(card.id, ""))
        for other in cards:
            if other.id == card.id:
                continue
            title = other.title.strip().lower()
            if len(title) >= 6 and title in text:
                add(
                    other.id,
                    card.id,
                    f"В описании упоминается «{other.title}»",
                    0.72,
                )

    for card in cards:
        for dep in card.depends_on or []:
            if dep in card_by_id:
                add(
                    dep,
                    card.id,
                    "Уже заданная связь",
                    1.0,
                )

    suggestions.sort(key=lambda s: (-s["confidence"], s["to_title"], s["from_title"]))
    return suggestions


def apply_dag_suggestions(
    board: KanbanBoard,
    suggestions: list[dict[str, Any]],
    *,
    min_confidence: float = 0.55,
) -> int:
    """Merge suggested edges into cards. Returns number of cards updated."""
    card_by_id = {c.id: c for c in board.cards}
    updated = 0
    for item in suggestions:
        if float(item.get("confidence") or 0) < min_confidence:
            continue
        to_id = str(item.get("to_card_id") or "").strip()
        from_id = str(item.get("from_card_id") or "").strip()
        card = card_by_id.get(to_id)
        if card is None or from_id == to_id:
            continue
        deps = list(card.depends_on or [])
        if from_id in deps:
            continue
        trial = deps + [from_id]
        if would_create_cycle(board.cards, to_id, trial):
            continue
        card.depends_on = trial
        updated += 1
    return updated
