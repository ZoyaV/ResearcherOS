"""Reconstruct koi Project models from Hub snapshot JSON."""

from __future__ import annotations

from koi.core.models import (
    ExperimentCard,
    KanbanBoard,
    KanbanColumn,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
    ResearchQuestionCertainty,
    Verdict,
)


def project_from_client(data: dict) -> Project:
    project_id = str(data.get("id") or "")
    nodes: list[Node] = []
    for raw in data.get("nodes") or []:
        questions: list[MethodResearchQuestion] = []
        for q in raw.get("research_questions") or []:
            questions.append(
                MethodResearchQuestion(
                    id=str(q.get("id") or ""),
                    question=str(q.get("question") or ""),
                    answer=str(q.get("answer") or ""),
                    narrative=str(q.get("narrative") or ""),
                    certainty=ResearchQuestionCertainty(
                        q.get("certainty") or ResearchQuestionCertainty.DEFINITE.value
                    ),
                    importance=int(q.get("importance") or 3),
                    card_id=q.get("card_id"),
                )
            )
        nodes.append(
            Node(
                id=str(raw["id"]),
                project_id=str(raw.get("project_id") or project_id),
                parent_id=raw.get("parent_id"),
                node_type=NodeType(raw["node_type"]),
                title=str(raw.get("title") or ""),
                description=str(raw.get("description") or ""),
                verdict=Verdict(raw.get("verdict") or Verdict.OPEN.value),
                research_questions=questions,
            )
        )

    boards: list[KanbanBoard] = []
    raw_boards = data.get("boards") or {}
    if isinstance(raw_boards, dict):
        board_values = raw_boards.values()
    else:
        board_values = raw_boards
    for raw_board in board_values:
        cards = [
            ExperimentCard(
                id=str(card.get("id") or ""),
                board_id=str(card.get("board_id") or raw_board.get("id") or ""),
                column_id=str(card.get("column_id") or ""),
                title=str(card.get("title") or ""),
                description=str(card.get("description") or ""),
                tags=list(card.get("tags") or []),
                depends_on=list(card.get("depends_on") or []),
                linked_node_id=card.get("linked_node_id"),
                created_at=card.get("created_at") or None,
                updated_at=card.get("updated_at") or None,
            )
            for card in raw_board.get("cards") or []
        ]
        boards.append(
            KanbanBoard(
                id=str(raw_board.get("id") or ""),
                owner_node_id=str(raw_board.get("owner_node_id") or ""),
                columns=[
                    KanbanColumn(
                        id=str(col.get("id") or ""),
                        title=str(col.get("title") or ""),
                        order=int(col.get("order") or 0),
                    )
                    for col in raw_board.get("columns") or []
                ],
                cards=cards,
            )
        )

    return Project(
        id=project_id,
        title=str(data.get("title") or project_id),
        description=str(data.get("description") or ""),
        literature_keywords=list(data.get("literature_keywords") or []),
        card_tags=list(data.get("card_tags") or []),
        nodes=nodes,
        boards=boards,
    )
