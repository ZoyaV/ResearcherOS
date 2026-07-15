"""Pure mutations of the Project aggregate, without persistence side effects."""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from koi.core.models import (
    ALLOWED_CHILDREN,
    DEFAULT_KANBAN_COLUMNS,
    KANBAN_OWNER_TYPES,
    KanbanBoard,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
)


def _ensure_board(project: Project, owner_node_id: str) -> KanbanBoard:
    existing = next(
        (board for board in project.boards if board.owner_node_id == owner_node_id),
        None,
    )
    if existing is not None:
        return existing
    board = KanbanBoard(
        id=f"board-{owner_node_id}",
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
    parent = next((node for node in project.nodes if node.id == parent_id), None)
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
    return node


def _validate_research_questions(
    project: Project,
    node: Node,
    questions: list[MethodResearchQuestion],
) -> list[MethodResearchQuestion]:
    if node.node_type != NodeType.METHOD:
        raise ValueError("Research questions are only allowed on method nodes")
    board = next(
        (item for item in project.boards if item.owner_node_id == node.id),
        None,
    )
    valid_card_ids = {card.id for card in board.cards} if board else set()
    cleaned: list[MethodResearchQuestion] = []
    for question_input in questions:
        question = question_input.question.strip()
        if not question:
            continue
        importance = max(1, min(5, int(question_input.importance)))
        card_id = (question_input.card_id or "").strip() or None
        if card_id and card_id not in valid_card_ids:
            raise ValueError(f"Unknown experiment card: {card_id}")
        cleaned.append(
            MethodResearchQuestion(
                id=question_input.id,
                question=question,
                answer=question_input.answer.strip(),
                narrative=question_input.narrative.strip(),
                certainty=question_input.certainty,
                importance=importance,
                card_id=card_id,
            )
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
    node = next(node for node in project.nodes if node.id == node_id)
    if title is not None:
        node.title = title
        if node.node_type == NodeType.PROBLEM:
            project.title = title
    if description is not None:
        node.description = description
    if research_questions is not None:
        node.research_questions = _validate_research_questions(
            project,
            node,
            research_questions,
        )
    return node


def delete_node(project: Project, node_id: str) -> None:
    node = next(item for item in project.nodes if item.id == node_id)
    if node.node_type == NodeType.PROBLEM:
        raise ValueError("Cannot delete problem node")

    to_remove = {node_id}

    def collect_children(parent_id: str) -> None:
        for item in project.nodes:
            if item.parent_id == parent_id:
                to_remove.add(item.id)
                collect_children(item.id)

    collect_children(node_id)
    project.nodes = [item for item in project.nodes if item.id not in to_remove]
    project.boards = [
        board for board in project.boards if board.owner_node_id not in to_remove
    ]


def update_board(project: Project, board: KanbanBoard) -> KanbanBoard:
    for index, existing in enumerate(project.boards):
        if existing.id == board.id:
            project.boards[index] = board
            return board
    raise ValueError("Board not found")

