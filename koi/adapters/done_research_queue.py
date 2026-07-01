"""Queue of kanban cards moved to done — for agent research-question generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypedDict

from koi.adapters.workspace import get_workspace

if TYPE_CHECKING:
    from koi.core.models import Project

_ws = get_workspace()
QUEUE_PATH = _ws.run_dir / "done-research-queue.json"


class DoneResearchItem(TypedDict):
    project_id: str
    board_id: str
    card_id: str
    enqueued_at: str


def _load() -> list[DoneResearchItem]:
    if not QUEUE_PATH.exists():
        return []
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item for item in data if _valid_item(item)]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save(items: list[DoneResearchItem]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _valid_item(item: object) -> bool:
    if not isinstance(item, dict):
        return False
    return all(
        isinstance(item.get(k), str) and item[k]
        for k in ("project_id", "board_id", "card_id", "enqueued_at")
    )


def _key(item: DoneResearchItem) -> tuple[str, str, str]:
    return (item["project_id"], item["board_id"], item["card_id"])


def enqueue_done_card(project_id: str, board_id: str, card_id: str) -> bool:
    """Add card to queue. Returns True if newly enqueued."""
    items = _load()
    key = (project_id, board_id, card_id)
    if any(_key(i) == key for i in items):
        return False
    items.append(
        {
            "project_id": project_id,
            "board_id": board_id,
            "card_id": card_id,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save(items)
    return True


def card_has_research_question(project: Project, board_id: str, card_id: str) -> bool:
    """True if the method already has an RQ linked to this card."""
    board = next((b for b in project.boards if b.id == board_id), None)
    if board is None:
        return False
    method = next((n for n in project.nodes if n.id == board.owner_node_id), None)
    if method is None:
        return False
    for q in method.research_questions:
        if q.card_id == card_id:
            return True
        answer = (q.answer or "").strip()
        if answer and card_id in answer:
            return True
    return False


def enqueue_done_card_if_needed(
    project: Project,
    board_id: str,
    card_id: str,
    *,
    card_title: str = "",
) -> bool:
    """Enqueue when card is done and has no RQ yet. Returns True if newly queued."""
    if card_has_research_question(project, board_id, card_id):
        return False
    board = next((b for b in project.boards if b.id == board_id), None)
    card = next((c for c in board.cards if c.id == card_id), None) if board else None
    title = card_title or (card.title if card else card_id)
    if not enqueue_done_card(project.id, board_id, card_id):
        return False
    try:
        from koi.adapters.project_sync_queue import enqueue_push

        enqueue_push(project.id, "card_done", f"карточка {card_id} ({title}) → done")
    except Exception:
        pass
    return True


def sync_done_research_on_save(before: Project | None, after: Project) -> None:
    """After save_project: queue cards that just moved to done."""
    if before is None:
        return
    old_cols = {
        (board.id, card.id): card.column_id
        for board in before.boards
        for card in board.cards
    }
    for board in after.boards:
        for card in board.cards:
            if card.column_id != "done":
                continue
            if old_cols.get((board.id, card.id)) == "done":
                continue
            enqueue_done_card_if_needed(
                after, board.id, card.id, card_title=card.title
            )


def reconcile_done_research_queue(project: Project) -> int:
    """Enqueue done cards without RQ (e.g. after direct project.md edit). Returns new count."""
    n = 0
    for board in project.boards:
        for card in board.cards:
            if card.column_id != "done":
                continue
            if enqueue_done_card_if_needed(
                project, board.id, card.id, card_title=card.title
            ):
                n += 1
    return n


def list_pending() -> list[DoneResearchItem]:
    return _load()


def dequeue(project_id: str, board_id: str, card_id: str) -> bool:
    items = _load()
    key = (project_id, board_id, card_id)
    next_items = [i for i in items if _key(i) != key]
    if len(next_items) == len(items):
        return False
    _save(next_items)
    return True
