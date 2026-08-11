"""Method milestones: koi-structure/reports/<method>/milestones.md"""

from __future__ import annotations

import re
import uuid
from datetime import date as date_cls
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from koi.adapters.card_reports import owner_slug_for_board, reports_dir, slugify_name
from koi.core.models import NodeType

if TYPE_CHECKING:
    from koi.core.models import Project

MILESTONES_FILENAME = "milestones.md"
HEADING_RE = re.compile(
    r"^##\s+(?P<date>\S+?)\s*[—\-|]\s*(?P<title>.+?)\s*$"
)
ID_COMMENT_RE = re.compile(r"<!--\s*id:\s*(?P<id>[^\s>]+)\s*-->", re.IGNORECASE)
CARD_LINE_RE = re.compile(
    r"^[-*]\s+(?:card:)?(?P<id>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:#.*)?$"
)


@dataclass
class Milestone:
    id: str
    date: str
    title: str
    card_ids: list[str] = field(default_factory=list)


class MilestoneError(ValueError):
    """Invalid milestone request."""


def new_milestone_id() -> str:
    return f"ms-{uuid.uuid4().hex[:8]}"


def parse_milestone_date(raw: str) -> date_cls | None:
    """Parse DD.MM.YY, DD.MM.YYYY, or YYYY-MM-DD into a date for sorting."""
    s = (raw or "").strip()
    if not s:
        return None
    for fmt, parts in (
        (r"^(\d{1,2})\.(\d{1,2})\.(\d{2})$", "dmy2"),
        (r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", "dmy4"),
        (r"^(\d{4})-(\d{1,2})-(\d{1,2})$", "ymd"),
    ):
        m = re.match(fmt, s)
        if not m:
            continue
        try:
            if parts == "dmy2":
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                y += 2000 if y < 100 else 0
            elif parts == "dmy4":
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            else:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date_cls(y, mo, d)
        except ValueError:
            continue
    return None


def sort_milestones(milestones: list[Milestone]) -> list[Milestone]:
    """Chronological order; undated / unparsable go last, stable by title then id."""
    indexed = list(enumerate(milestones))

    def key(item: tuple[int, Milestone]) -> tuple:
        i, ms = item
        parsed = parse_milestone_date(ms.date)
        # False sorts before True → dated first
        return (parsed is None, parsed or date_cls.max, (ms.title or "").lower(), ms.id, i)

    return [ms for _, ms in sorted(indexed, key=key)]



def method_reports_dir(project: Project, node_id: str) -> Path:
    node = next((n for n in project.nodes if n.id == node_id), None)
    if node is None or node.node_type != NodeType.METHOD:
        raise MilestoneError("Method node not found")
    board = next((b for b in project.boards if b.owner_node_id == node_id), None)
    if board is not None:
        slug = owner_slug_for_board(project, board.id)
    else:
        slug = slugify_name(node.title)
    path = reports_dir(project.id) / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def milestones_path(project: Project, node_id: str) -> Path:
    return method_reports_dir(project, node_id) / MILESTONES_FILENAME


def relative_milestones_path(project: Project, node_id: str) -> str:
    path = milestones_path(project, node_id)
    root = reports_dir(project.id)
    return path.relative_to(root).as_posix()


def parse_milestones_md(text: str) -> list[Milestone]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    milestones: list[Milestone] = []
    current: Optional[Milestone] = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            milestones.append(current)
            current = None

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("## "):
            flush()
            match = HEADING_RE.match(stripped)
            if match:
                date = match.group("date").strip()
                title = match.group("title").strip()
            else:
                rest = stripped[3:].strip()
                if "—" in rest:
                    date, _, title = rest.partition("—")
                elif "|" in rest:
                    date, _, title = rest.partition("|")
                elif " - " in rest:
                    date, _, title = rest.partition(" - ")
                else:
                    date, title = "", rest
                date = date.strip()
                title = title.strip() or "Milestone"
            ms_id = new_milestone_id()
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                id_match = ID_COMMENT_RE.search(lines[j])
                if id_match:
                    ms_id = id_match.group("id").strip()
                    i = j
            current = Milestone(id=ms_id, date=date, title=title, card_ids=[])
        elif current is not None:
            card_match = CARD_LINE_RE.match(stripped)
            if card_match:
                card_id = card_match.group("id").strip()
                if card_id and card_id not in current.card_ids:
                    current.card_ids.append(card_id)
        i += 1

    flush()
    return sort_milestones(milestones)


def format_milestones_md(milestones: list[Milestone]) -> str:
    milestones = sort_milestones(list(milestones))
    parts = [
        "# Milestones",
        "",
        "<!-- Method timeline: date, name, linked kanban card ids. -->",
        "",
    ]
    if not milestones:
        parts.append("")
        return "\n".join(parts)

    for ms in milestones:
        date = (ms.date or "").strip() or "??.??.??"
        title = (ms.title or "").strip() or "Milestone"
        parts.append(f"## {date} — {title}")
        parts.append(f"<!-- id: {ms.id} -->")
        parts.append("")
        if ms.card_ids:
            for card_id in ms.card_ids:
                cid = str(card_id).strip()
                if cid:
                    parts.append(f"- {cid}")
            parts.append("")
        else:
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def milestone_to_dict(ms: Milestone) -> dict:
    return {
        "id": ms.id,
        "date": ms.date,
        "title": ms.title,
        "card_ids": list(ms.card_ids),
    }


def milestones_from_payload(items: list[dict]) -> list[Milestone]:
    result: list[Milestone] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip() or "Milestone"
        date = str(item.get("date") or "").strip()
        raw_id = str(item.get("id") or "").strip() or new_milestone_id()
        if raw_id in seen_ids:
            raw_id = new_milestone_id()
        seen_ids.add(raw_id)
        card_ids: list[str] = []
        for raw in item.get("card_ids") or []:
            cid = str(raw).strip()
            if cid and cid not in card_ids:
                card_ids.append(cid)
        result.append(Milestone(id=raw_id, date=date, title=title, card_ids=card_ids))
    return sort_milestones(result)


def load_milestones(project: Project, node_id: str) -> tuple[bool, list[Milestone], str]:
    path = milestones_path(project, node_id)
    rel = relative_milestones_path(project, node_id)
    if not path.is_file():
        return False, [], rel
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise MilestoneError(f"Cannot read milestones.md: {error}") from error
    return True, parse_milestones_md(text), rel


def create_milestones_file(project: Project, node_id: str) -> tuple[list[Milestone], str]:
    path = milestones_path(project, node_id)
    rel = relative_milestones_path(project, node_id)
    if path.is_file():
        exists, milestones, _ = load_milestones(project, node_id)
        if exists:
            return milestones, rel
    path.write_text(format_milestones_md([]), encoding="utf-8")
    return [], rel


def save_milestones(
    project: Project, node_id: str, milestones: list[Milestone]
) -> tuple[list[Milestone], str]:
    path = milestones_path(project, node_id)
    rel = relative_milestones_path(project, node_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sort_milestones(list(milestones))
    path.write_text(format_milestones_md(ordered), encoding="utf-8")
    return ordered, rel
