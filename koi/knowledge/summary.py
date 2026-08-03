"""Structured knowledge read model used by the API dashboard."""

from __future__ import annotations

from koi.core.models import NodeType, Project
from koi.knowledge.model import VERDICT_MARK, methods_under, shorten, statistics


def build_summary(
    project: Project,
    *,
    report_index: dict,
    documents: list,
    recent_log: list[dict],
    pages: list | None = None,
) -> dict:
    page_docs = pages or []
    causes, supported, refuted, insights_total = statistics(project)
    problem = next(
        (node for node in project.nodes if node.node_type == NodeType.PROBLEM), None
    )
    hypotheses = []
    for cause in causes:
        items = []
        for method in methods_under(project.nodes, cause.id):
            for question in method.research_questions:
                report = report_index.get(question.card_id) if question.card_id else None
                items.append(
                    {
                        "id": question.id,
                        "question": question.question,
                        "narrative": question.narrative or question.answer,
                        "answer": question.answer,
                        "certainty": question.certainty.value,
                        "importance": question.importance,
                        "card_id": question.card_id,
                        "method_id": method.id,
                        "method_title": method.title,
                        "report": f"reports/{report}" if report else None,
                    }
                )
        items.sort(key=lambda item: item["importance"], reverse=True)
        hypotheses.append(
            {
                "id": cause.id,
                "title": cause.title,
                "description": shorten(cause.description, 280),
                "verdict": cause.verdict.value,
                "insights": items,
            }
        )

    return {
        "project_id": project.id,
        "title": project.title,
        "problem": (
            {"title": problem.title, "summary": shorten(problem.description, 400)}
            if problem
            else None
        ),
        "stats": {
            "hypotheses": len(causes),
            "supported": supported,
            "refuted": refuted,
            "open": len(causes) - supported - refuted,
            "insights": insights_total,
            "docs": len(documents),
            "reports": len(report_index),
            "pages": len(page_docs),
        },
        "docs": [
            {
                "path": f"knowledge/{document.name}",
                "name": document.name,
                "title": document.title,
                "summary": document.summary,
                "generated": document.name == "hypotheses.md",
            }
            for document in documents
        ],
        "pages": [
            {
                "id": page.get("id"),
                "title": page.get("title") or page.get("slug") or page.get("id"),
                "slug": page.get("slug") or "",
                "path": page.get("path") or "",
            }
            for page in page_docs
        ],
        "hypotheses": hypotheses,
        "log_recent": recent_log,
    }
