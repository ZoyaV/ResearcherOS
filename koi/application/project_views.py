"""Frontend-facing project read models shared by API and Hub."""

from __future__ import annotations

from koi.core.models import ALLOWED_CHILDREN, KANBAN_OWNER_TYPES, NodeType, Project


def project_to_client(project: Project) -> dict:
    boards_by_owner = {board.owner_node_id: board for board in project.boards}
    nodes_out = []
    for node in project.nodes:
        item = node.model_dump()
        item["node_type"] = node.node_type.value
        item["verdict"] = node.verdict.value
        if node.node_type in KANBAN_OWNER_TYPES:
            board = boards_by_owner.get(node.id)
            item["has_kanban"] = board is not None
            item["board_id"] = board.id if board else None
            item["has_research_questions"] = len(node.research_questions) > 0
            counts = {"definite": 0, "tentative": 0}
            for question in node.research_questions:
                counts[question.certainty.value] += 1
            item["research_question_counts"] = counts
            cards_by_id = {card.id: card for card in board.cards} if board else {}
            item["research_questions"] = [
                {
                    "id": question.id,
                    "question": question.question,
                    "answer": question.answer,
                    "narrative": question.narrative,
                    "certainty": question.certainty.value,
                    "importance": question.importance,
                    "card_id": question.card_id,
                    "card_title": (
                        cards_by_id[question.card_id].title
                        if question.card_id and question.card_id in cards_by_id
                        else None
                    ),
                }
                for question in node.research_questions
            ]
        else:
            item["has_kanban"] = False
            item["board_id"] = None
            item["has_research_questions"] = False
            item["research_question_counts"] = {"definite": 0, "tentative": 0}
            item["research_questions"] = []
        if node.node_type in (NodeType.CAUSE_EVIDENCE, NodeType.REMEDIATION):
            item["can_add_method"] = True
        nodes_out.append(item)

    boards_out = {
        board.id: {
            "id": board.id,
            "owner_node_id": board.owner_node_id,
            "source_project_id": project.id,
            "columns": [column.model_dump() for column in board.columns],
            "cards": [card.model_dump() for card in board.cards],
        }
        for board in project.boards
    }

    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "literature_keywords": list(project.literature_keywords),
        "card_tags": list(project.card_tags),
        "nodes": nodes_out,
        "boards": boards_out,
    }


def allowed_children(parent_type: str | None) -> list[str]:
    key = NodeType(parent_type) if parent_type else None
    return [node_type.value for node_type in ALLOWED_CHILDREN.get(key, [])]
