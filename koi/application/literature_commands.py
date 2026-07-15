"""Application use cases for turning literature results into research projects."""

from __future__ import annotations

from dataclasses import dataclass, field

from koi.adapters import card_reports, repository
from koi.core.models import ExperimentCard, NodeType, Project
from koi.services import literature


@dataclass(frozen=True)
class CreateReviewSetCommand:
    query: str
    limit: int = 10
    papers: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewSetResult:
    project: Project
    query: str
    count: int


def create_review_set(command: CreateReviewSetCommand) -> ReviewSetResult:
    query = command.query.strip()
    if not query:
        raise ValueError("Query must not be empty")

    results = command.papers or literature.search_library(query, limit=command.limit)
    if not results:
        raise ValueError("No ranked papers available for this query")

    project = repository.create_project(literature.review_project_title(query))
    project.description = literature.review_project_description(query, len(results))
    root = next(
        (node for node in project.nodes if node.node_type == NodeType.PROBLEM),
        None,
    )
    if root is None:
        raise RuntimeError("Problem node missing in generated project")
    root.description = project.description
    repository.save_project(project)

    cause = repository.add_node(
        project,
        root.id,
        NodeType.CAUSE,
        "Candidate papers retrieved from the local library",
        "Auto-generated set of papers ranked against the current research question.",
    )
    evidence = repository.add_node(
        project,
        cause.id,
        NodeType.CAUSE_EVIDENCE,
        "Evidence of relevance for the research question",
        f"Query: {query}",
    )
    method = repository.add_node(
        project,
        evidence.id,
        NodeType.METHOD,
        "Screen, annotate, and shortlist the papers",
        "Each card corresponds to one ranked paper. Use the report to capture screening notes.",
    )

    board = next(
        (item for item in project.boards if item.owner_node_id == method.id),
        None,
    )
    if board is None:
        raise RuntimeError("Review board was not created")

    board.cards = [
        ExperimentCard(
            id=literature.review_card_id(),
            board_id=board.id,
            column_id="backlog",
            title=str(result["title"]),
            description=str(result["arxiv_url"]),
        )
        for result in results
    ]
    repository.update_board(project, board)

    for card, result in zip(board.cards, results):
        card_reports.write_report(
            project,
            board.id,
            card.id,
            card.title,
            literature.build_review_report(result, query),
        )

    return ReviewSetResult(project=project, query=query, count=len(results))
