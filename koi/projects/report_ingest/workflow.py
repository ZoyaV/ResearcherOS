"""Apply parsed report claims to a project and persist the result."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from koi.adapters.card_reports import ensure_card_report, load_index
from koi.adapters.repository import load_project, save_project
from koi.core.models import Node, NodeType, Project, Verdict
from koi.projects.report_ingest.models import ReportIngestError
from koi.projects.report_ingest.parsing import build_questions, parse_run_report


RUN_SUFFIX = ".run.md"


def _find_node(project: Project, node_id: str) -> Optional[Node]:
    return next((node for node in project.nodes if node.id == node_id), None)


def ingest_report(
    project_id: str, report_path: str | Path, *, dry_run: bool = False
) -> dict:
    path = Path(report_path)
    if not path.is_file():
        raise ReportIngestError(f"Файл отчёта не найден: {path}")
    claim = parse_run_report(path.read_text(encoding="utf-8"))
    project = load_project(project_id)
    if project is None:
        raise ReportIngestError(f"Проект не найден: {project_id}")

    method = _find_node(project, claim.method_id)
    if method is None or method.node_type != NodeType.METHOD:
        raise ReportIngestError(f"Узел-метод не найден: {claim.method_id}")
    board = next(
        (candidate for candidate in project.boards if candidate.owner_node_id == method.id),
        None,
    )
    card = (
        next((candidate for candidate in board.cards if candidate.id == claim.card_id), None)
        if board
        else None
    )
    if card is None:
        raise ReportIngestError(
            f"Карточка {claim.card_id} не найдена на доске метода {method.id}"
        )

    summary: dict = {
        "project": project_id,
        "report": str(path),
        "cause_id": claim.cause_id,
        "method_id": method.id,
        "card_id": card.id,
        "warnings": list(claim.warnings),
        "dry_run": dry_run,
    }
    if claim.verdict and claim.cause_id:
        cause = _find_node(project, claim.cause_id)
        if cause is None:
            claim.warnings.append(f"Узел гипотезы не найден: {claim.cause_id}")
            summary["verdict"] = None
        else:
            if cause.node_type != NodeType.CAUSE:
                claim.warnings.append(
                    f"{claim.cause_id} имеет тип {cause.node_type}, не cause"
                )
            summary["verdict"] = {
                "node": cause.id,
                "old": cause.verdict.value,
                "new": claim.verdict,
            }
            if not dry_run:
                cause.verdict = Verdict(claim.verdict)
    else:
        summary["verdict"] = None

    new_questions = build_questions(claim)
    kept = [question for question in method.research_questions if question.card_id != card.id]
    summary["insights"] = {
        "added": [question.id for question in new_questions],
        "kept": [question.id for question in kept],
        "dropped": [],
    }
    if not dry_run:
        method.research_questions = kept + new_questions

    summary["card_moved"] = {"old": card.column_id, "new": "done"}
    if not dry_run:
        card.column_id = "done"
        ensure_card_report(project, board.id, card.id, card.title)
    summary["public_report"] = load_index(project_id).get(card.id)

    if not dry_run:
        save_project(project)
        summary["knowledge_updated"] = True
    summary["warnings"] = list(claim.warnings)
    return summary


def expected_run_report_path(
    project: Project, board_id: str, card_id: str, card_title: str
) -> Path:
    public = ensure_card_report(project, board_id, card_id, card_title)
    return public.with_name(public.name[: -len(".md")] + RUN_SUFFIX)
