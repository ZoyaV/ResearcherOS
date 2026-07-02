"""File-based project storage under ``<repo>/koi-structure/project.md``."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from uuid import uuid4

import yaml

from koi.adapters.paths import koi_root, project_md
from koi.adapters.project_mount import (
    get_mount,
    list_mounts,
    rescan_projects,
    scan_roots,
)
from koi.core.migrate import ensure_project_structure, kanban_md_needs_upgrade
from koi.core.md_io import normalize_kanban_board, parse_project_md, serialize_project_md
from koi.adapters.research_store import (
    apply_research_to_project,
    load_research_questions,
    md_has_legacy_question_blocks,
    merge_research_from_md,
    research_path,
    save_research,
)
from koi.core.models import (
    ALLOWED_CHILDREN,
    DEFAULT_KANBAN_COLUMNS,
    KANBAN_OWNER_TYPES,
    MAX_METHOD_RESEARCH_QUESTIONS,
    KanbanBoard,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
)


def _slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:48] or "project"


def _project_path(project_id: str) -> Path:
    return project_md(project_id)


def _read_meta(text: str) -> tuple[dict, str]:
    from koi.core.md_io import _split_frontmatter

    return _split_frontmatter(text)


def seed_templates() -> None:
    """No-op: demo projects are seeded via ``scripts/koi_seed_demo.py`` if needed."""


def list_projects(*, with_programs: bool = False) -> list[dict]:
    items = []
    preferred = {"ai-agents-embodied": 0, "demo-aggregation": 1}
    mounts = sorted(
        list_mounts(),
        key=lambda m: (preferred.get(m.project_id, 99), m.project_id),
    )
    for mount in mounts:
        md = mount.koi_root / "project.md"
        if not md.exists():
            continue
        text = md.read_text(encoding="utf-8")
        meta, _ = _read_meta(text)
        items.append(
            {
                "id": meta.get("id", mount.project_id),
                "title": meta.get("title", mount.project_id),
                "updated": meta.get("updated"),
            }
        )
    if with_programs:
        from koi.services.programs import enrich_projects

        return enrich_projects(items)
    return items


def load_project(project_id: str, *, sync_reports: bool = False) -> Optional[Project]:
    if get_mount(project_id) is None:
        return None
    path = _project_path(project_id)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    project = parse_project_md(text, project_id=project_id)
    migrated_research = False
    if research_path(project_id).exists():
        apply_research_to_project(project, load_research_questions(project_id))
        if md_has_legacy_question_blocks(text):
            migrated_research = True
    else:
        migrated_research = merge_research_from_md(project)
    kanban_upgrade = kanban_md_needs_upgrade(text)
    if ensure_project_structure(project) or migrated_research or kanban_upgrade:
        save_project(project)
    if sync_reports:
        from koi.adapters.card_reports import sync_reports_for_project

        sync_reports_for_project(project)
    from koi.adapters.done_research_queue import reconcile_done_research_queue

    reconcile_done_research_queue(project)
    return project


def _merge_preserved_frontmatter(text: str, path: Path) -> str:
    """Keep organizational fields that serialize_project_md does not emit."""
    if not path.exists():
        return text
    old_meta, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    meta, body = _split_frontmatter(text)
    for key in ("programs", "code_root", "literature_keywords"):
        if key in old_meta and key not in meta:
            meta[key] = old_meta[key]
    return (
        "---\n"
        + yaml.dump(meta, allow_unicode=True, sort_keys=False).strip()
        + "\n---\n\n"
        + body
    )


def _project_snapshot(project_id: str) -> Optional[Project]:
    """Parse on-disk project.md without migrations or research side effects."""
    path = _project_path(project_id)
    if not path.exists():
        return None
    return parse_project_md(path.read_text(encoding="utf-8"), project_id=project_id)


def save_project(project: Project) -> Path:
    mount = get_mount(project.id)
    if mount is None:
        raise KeyError(f"Project not found: {project.id}")
    before = _project_snapshot(project.id)
    for board in project.boards:
        normalize_kanban_board(board)
    folder = mount.koi_root
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "project.md"
    text = serialize_project_md(project)
    path.write_text(_merge_preserved_frontmatter(text, path), encoding="utf-8")
    from koi.adapters.done_research_queue import sync_done_research_on_save

    sync_done_research_on_save(before, project)
    save_research(project)
    try:
        from koi.services.knowledge import write_project_knowledge

        write_project_knowledge(project)
    except Exception:  # noqa: BLE001 — KB is a derived artifact, not source of truth
        pass
    return path


def _allocate_repo_root(project_id: str) -> Path:
    roots = scan_roots()
    if not roots:
        raise RuntimeError("No scan roots configured")
    scan_root = roots[0]
    base_folder = project_id.replace("-", "_")
    n = 0
    while True:
        folder_name = base_folder if n == 0 else f"{base_folder}_{n}"
        repo_root = scan_root / folder_name
        if not repo_root.exists():
            return repo_root
        n += 1


def _split_frontmatter(text: str) -> tuple[dict, str]:
    from koi.core.md_io import _split_frontmatter as split

    return split(text)


def _validate_project_tag(tag: str) -> str:
    cleaned = tag.strip()
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", cleaned):
        raise ValueError(
            "Tag must start with a letter and contain only English letters, digits, _ or -"
        )
    return cleaned.lower()


def _apply_project_frontmatter_extras(
    koi: Path, *, programs: list[str] | None = None
) -> None:
    path = koi / "project.md"
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    if programs:
        meta["programs"] = programs
    meta["code_root"] = "../projectcode"
    path.write_text(
        "---\n"
        + yaml.dump(meta, allow_unicode=True, sort_keys=False).strip()
        + "\n---\n\n"
        + body,
        encoding="utf-8",
    )


def _repo_root_for_tag(project_id: str) -> Path:
    return scan_roots()[0] / project_id.replace("-", "_")


def create_project(
    title: str,
    *,
    project_id: str | None = None,
    description: str = "",
    programs: list[str] | None = None,
) -> Project:
    desc = description.strip()
    if project_id:
        pid = _validate_project_tag(project_id)
        if get_mount(pid) is not None:
            raise ValueError(f"Project already exists: {pid}")
        repo_root = _repo_root_for_tag(pid)
        if repo_root.exists():
            raise ValueError(f"Project folder already exists: {repo_root.name}")
    else:
        base_id = _slugify(title)
        pid = base_id
        n = 1
        while get_mount(pid) is not None:
            pid = f"{base_id}-{n}"
            n += 1
        repo_root = _allocate_repo_root(pid)

    koi = repo_root / "koi-structure"
    code = repo_root / "projectcode"
    koi.mkdir(parents=True)
    code.mkdir(parents=True)
    (code / "README.md").write_text(
        "# Project code\n\nExperiment scripts and implementation live here.\n",
        encoding="utf-8",
    )
    (koi / "research.json").write_text(
        json.dumps({"version": 1, "questions": []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    problem_id = "problem"
    project = Project(id=pid, title=title, description=desc)
    project.nodes = [
        Node(
            id=problem_id,
            project_id=pid,
            parent_id=None,
            node_type=NodeType.PROBLEM,
            title=title,
            description=desc,
        )
    ]
    project.boards = []
    for board in project.boards:
        normalize_kanban_board(board)
    (koi / "project.md").write_text(serialize_project_md(project), encoding="utf-8")
    _apply_project_frontmatter_extras(koi, programs=programs or [])
    rescan_projects()
    save_project(project)
    return project


def _boards_index(project: Project) -> dict[str, KanbanBoard]:
    return {b.owner_node_id: b for b in project.boards}


def _ensure_board(project: Project, owner_node_id: str) -> KanbanBoard:
    by_owner = _boards_index(project)
    if owner_node_id in by_owner:
        return by_owner[owner_node_id]
    node = next(n for n in project.nodes if n.id == owner_node_id)
    board_id = f"board-{owner_node_id}"
    board = KanbanBoard(
        id=board_id,
        owner_node_id=owner_node_id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[],
    )
    project.boards.append(board)
    return board


def add_node(
    project: Project,
    parent_id: str,
    node_type: NodeType,
    title: str,
    description: str = "",
) -> Node:
    parent = next((n for n in project.nodes if n.id == parent_id), None)
    if parent is None:
        raise ValueError("Parent not found")
    allowed = ALLOWED_CHILDREN.get(parent.node_type, [])
    if node_type not in allowed:
        raise ValueError(f"Cannot add {node_type} under {parent.node_type}")

    node = Node(
        id=f"n-{uuid4().hex[:8]}",
        project_id=project.id,
        parent_id=parent_id,
        node_type=node_type,
        title=title,
        description=description,
    )
    project.nodes.append(node)
    if node_type in KANBAN_OWNER_TYPES:
        _ensure_board(project, node.id)
    save_project(project)
    return node


def _validate_research_questions(
    project: Project,
    node: Node,
    questions: list[MethodResearchQuestion],
) -> list[MethodResearchQuestion]:
    if node.node_type != NodeType.METHOD:
        raise ValueError("Research questions are only allowed on method nodes")
    if len(questions) > MAX_METHOD_RESEARCH_QUESTIONS:
        raise ValueError(
            f"At most {MAX_METHOD_RESEARCH_QUESTIONS} research questions per method"
        )
    board = next((b for b in project.boards if b.owner_node_id == node.id), None)
    valid_card_ids = {c.id for c in board.cards} if board else set()
    cleaned: list[MethodResearchQuestion] = []
    for q in questions:
        question = q.question.strip()
        if not question:
            continue
        importance = max(1, min(5, int(q.importance)))
        card_id = (q.card_id or "").strip() or None
        if card_id and card_id not in valid_card_ids:
            raise ValueError(f"Unknown experiment card: {card_id}")
        cleaned.append(
            MethodResearchQuestion(
                id=q.id,
                question=question,
                answer=q.answer.strip(),
                narrative=q.narrative.strip(),
                certainty=q.certainty,
                importance=importance,
                card_id=card_id,
            )
        )
    if len(cleaned) > MAX_METHOD_RESEARCH_QUESTIONS:
        raise ValueError(
            f"At most {MAX_METHOD_RESEARCH_QUESTIONS} research questions per method"
        )
    return cleaned


def update_node(
    project: Project,
    node_id: str,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    research_questions: Optional[list[MethodResearchQuestion]] = None,
) -> Node:
    node = next(n for n in project.nodes if n.id == node_id)
    if title is not None:
        node.title = title
        if node.node_type == NodeType.PROBLEM:
            project.title = title
    if description is not None:
        node.description = description
    if research_questions is not None:
        node.research_questions = _validate_research_questions(
            project, node, research_questions
        )
    save_project(project)
    return node


def delete_node(project: Project, node_id: str) -> None:
    node = next(n for n in project.nodes if n.id == node_id)
    if node.node_type == NodeType.PROBLEM:
        raise ValueError("Cannot delete problem node")

    to_remove = {node_id}

    def collect_children(pid: str) -> None:
        for n in project.nodes:
            if n.parent_id == pid:
                to_remove.add(n.id)
                collect_children(n.id)

    collect_children(node_id)
    project.nodes = [n for n in project.nodes if n.id not in to_remove]
    project.boards = [b for b in project.boards if b.owner_node_id not in to_remove]
    save_project(project)


def update_board(project: Project, board: KanbanBoard) -> KanbanBoard:
    for i, b in enumerate(project.boards):
        if b.id == board.id:
            project.boards[i] = board
            save_project(project)
            return board
    raise ValueError("Board not found")
