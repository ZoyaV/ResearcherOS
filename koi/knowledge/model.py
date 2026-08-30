"""Pure tree traversal and statistics shared by knowledge read models."""

from __future__ import annotations

from dataclasses import dataclass

from koi.core.models import NodeType, Project, Verdict


VERDICT_MARK = {
    Verdict.SUPPORTED: "✔ supported",
    Verdict.REFUTED: "✗ refuted",
    Verdict.OPEN: "… open",
}


@dataclass(frozen=True)
class KnowledgeDocument:
    name: str
    title: str
    summary: str


def children(nodes, parent_id):
    return [node for node in nodes if node.parent_id == parent_id]


def methods_under(nodes, cause_id):
    """Return method nodes below cause evidence and remediation nodes."""
    methods = []
    for intermediate in children(nodes, cause_id):
        for method in children(nodes, intermediate.id):
            if method.node_type == NodeType.METHOD:
                methods.append(method)
    return methods


def shorten(text: str, limit: int = 180) -> str:
    normalized = " ".join((text or "").split())
    return (
        normalized
        if len(normalized) <= limit
        else normalized[: limit - 1].rstrip() + "…"
    )


def causes(project: Project):
    return sorted(
        (node for node in project.nodes if node.node_type == NodeType.CAUSE),
        key=lambda node: node.title,
    )


def statistics(project: Project):
    project_causes = causes(project)
    supported = sum(
        1 for cause in project_causes if cause.verdict == Verdict.SUPPORTED
    )
    refuted = sum(1 for cause in project_causes if cause.verdict == Verdict.REFUTED)
    insights = sum(
        len(method.research_questions)
        for cause in project_causes
        for method in methods_under(project.nodes, cause.id)
    )
    return project_causes, supported, refuted, insights
