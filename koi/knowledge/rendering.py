"""Deterministic Markdown rendering for project knowledge artifacts."""

from __future__ import annotations

from koi.core.models import NodeType, Project
from koi.knowledge.model import (
    KnowledgeDocument,
    VERDICT_MARK,
    methods_under,
    shorten,
    statistics,
)


GENERATED_DOC = "hypotheses.md"


def render_hypotheses(project: Project, report_index: dict) -> str:
    nodes = project.nodes
    causes, supported, refuted, insights = statistics(project)
    lines = [
        "# Hypotheses and results",
        "",
        f"Automatically generated summary of {len(causes)} hypotheses "
        f"(supported: {supported}, refuted: {refuted}, "
        f"open: {len(causes) - supported - refuted}; insights: {insights}). "
        "Sources: project.md and research.json. Rebuilt whenever the project is "
        "saved; do not edit manually.",
        "",
    ]
    for cause in causes:
        mark = VERDICT_MARK.get(cause.verdict, cause.verdict.value)
        lines += [
            f"## {cause.title}",
            "",
            f"Verdict: {mark}  ·  node `{cause.id}`",
            "",
        ]
        if cause.description:
            lines += [cause.description, ""]
        had_insights = False
        for method in methods_under(nodes, cause.id):
            for question in method.research_questions:
                had_insights = True
                source = f"method `{method.id}`"
                if question.card_id:
                    source += f", card `{question.card_id}`"
                    report = report_index.get(question.card_id)
                    if report:
                        source += f" → [report](../reports/{report})"
                narrative = question.narrative or question.answer or "—"
                lines += [
                    f"- {question.question}",
                    f"  - {narrative}  _(certainty: {question.certainty.value}, "
                    f"importance: {question.importance}/5; {source})_",
                ]
        if not had_insights:
            lines.append("- _No insights yet (the experiment is not complete)._")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_project_index(
    project: Project,
    report_index: dict,
    documents: list[KnowledgeDocument],
) -> str:
    causes, supported, refuted, insights = statistics(project)
    problem = next(
        (node for node in project.nodes if node.node_type == NodeType.PROBLEM), None
    )
    lines = [
        f"# Knowledge base: {project.title}",
        "",
        "Project knowledge-base index with summaries and links. Full documents are ",
        "in [`knowledge/`](knowledge/), and the update log is in ",
        "[KNOWLEDGE_LOG.md](KNOWLEDGE_LOG.md). Generated automatically whenever ",
        "the project is saved (`koi/knowledge/`); do not edit manually.",
        "",
        f"Project: `{project.id}` · hypotheses: {len(causes)} "
        f"(✔ {supported} · ✗ {refuted} · … {len(causes) - supported - refuted}) "
        f"· insights: {insights} · documents: {len(documents)}",
        "",
    ]
    if problem:
        lines += [
            "## Problem",
            "",
            f"**{problem.title}.** {shorten(problem.description, 400)}",
            "",
        ]
    lines += ["## Documents", ""]
    if not documents:
        lines += [
            "_No documents yet. Add .md files to `knowledge/` "
            "(see the convention in docs/research-workflow.md)._",
            "",
        ]
    for document in documents:
        entry = f"- [{document.title}](knowledge/{document.name})"
        if document.summary:
            entry += f" — {document.summary}"
        lines.append(entry)
    lines.append("")
    lines += ["## Hypothesis status", ""]
    if not causes:
        lines += ["_No hypotheses yet._", ""]
    for cause in causes:
        mark = VERDICT_MARK.get(cause.verdict, cause.verdict.value)
        questions = [
            question
            for method in methods_under(project.nodes, cause.id)
            for question in method.research_questions
        ]
        entry = f"- {mark} — [{cause.title}](knowledge/{GENERATED_DOC})"
        if questions:
            entry += f" · insights: {len(questions)}"
        report = next(
            (
                report_index[question.card_id]
                for question in questions
                if question.card_id and question.card_id in report_index
            ),
            None,
        )
        if report:
            entry += f" · [report](reports/{report})"
        lines.append(entry)
        if questions:
            top = max(questions, key=lambda question: question.importance)
            text = top.narrative or top.answer
            if text:
                lines.append(f"  - conclusion: {shorten(text, 200)}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
