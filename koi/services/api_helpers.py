"""Serialize projects for the REST API / frontend."""

from __future__ import annotations

from koi.core.models import KANBAN_OWNER_TYPES, NodeType, Project


def project_to_client(project: Project) -> dict:
    boards_by_owner = {b.owner_node_id: b for b in project.boards}
    nodes_out = []
    for n in project.nodes:
        d = n.model_dump()
        d["node_type"] = n.node_type.value
        d["verdict"] = n.verdict.value
        if n.node_type in KANBAN_OWNER_TYPES:
            board = boards_by_owner.get(n.id)
            d["has_kanban"] = board is not None
            d["board_id"] = board.id if board else None
            d["has_research_questions"] = len(n.research_questions) > 0
            counts = {"definite": 0, "tentative": 0}
            for q in n.research_questions:
                if q.certainty.value == "definite":
                    counts["definite"] += 1
                else:
                    counts["tentative"] += 1
            d["research_question_counts"] = counts
            cards_by_id = {c.id: c for c in board.cards} if board else {}
            d["research_questions"] = [
                {
                    "id": q.id,
                    "question": q.question,
                    "answer": q.answer,
                    "narrative": q.narrative,
                    "certainty": q.certainty.value,
                    "importance": q.importance,
                    "card_id": q.card_id,
                    "card_title": (
                        cards_by_id[q.card_id].title
                        if q.card_id and q.card_id in cards_by_id
                        else None
                    ),
                }
                for q in n.research_questions
            ]
        else:
            d["has_kanban"] = False
            d["board_id"] = None
            d["has_research_questions"] = False
            d["research_question_counts"] = {"definite": 0, "tentative": 0}
            d["research_questions"] = []
        if n.node_type in (NodeType.CAUSE_EVIDENCE, NodeType.REMEDIATION):
            d["can_add_method"] = True
        nodes_out.append(d)

    boards_out = {}
    for b in project.boards:
        boards_out[b.id] = {
            "id": b.id,
            "owner_node_id": b.owner_node_id,
            "columns": [c.model_dump() for c in b.columns],
            "cards": [c.model_dump() for c in b.cards],
        }

    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "literature_keywords": list(project.literature_keywords),
        "nodes": nodes_out,
        "boards": boards_out,
    }


def allowed_children(parent_type: str | None) -> list[str]:
    key = NodeType(parent_type) if parent_type else None
    from koi.core.models import ALLOWED_CHILDREN

    return [t.value for t in ALLOWED_CHILDREN.get(key, [])]
