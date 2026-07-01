from __future__ import annotations

from pathlib import Path

from koi.adapters.paths import paper_answers_dir, paper_reviews_dir, reports_dir
from koi.services.literature import search_library
from koi.services.review.models import (
    ABSTRACT_BLOCK_RE,
    ARXIV_RE,
    MATCHED_TERMS_RE,
    QUERY_RE,
    REPORT_TITLE_RE,
    SCORE_RE,
    ReviewPaper,
)
from koi.services.review.util import _normalize_text, _read_json

def parse_review_report_markdown(text: str, source_report: str) -> ReviewPaper | None:
    title_match = REPORT_TITLE_RE.search(text)
    arxiv_match = ARXIV_RE.search(text)
    query_match = QUERY_RE.search(text)
    if not title_match or not arxiv_match:
        return None

    score_match = SCORE_RE.search(text)
    terms_match = MATCHED_TERMS_RE.search(text)
    abstract_match = ABSTRACT_BLOCK_RE.search(text)
    score: float | None = None
    if score_match:
        try:
            score = float(score_match.group(1).strip())
        except ValueError:
            score = None

    matched_terms = ()
    if terms_match:
        raw = terms_match.group(1).strip()
        if raw and raw.lower() != "n/a":
            matched_terms = tuple(x.strip() for x in raw.split(",") if x.strip())

    return ReviewPaper(
        title=title_match.group(1).strip(),
        arxiv_url=arxiv_match.group(1).strip(),
        query=query_match.group(1).strip() if query_match else "",
        score=score,
        abstract=_normalize_text(abstract_match.group(1)) if abstract_match else "",
        matched_terms=matched_terms,
        source_report=source_report,
    )


def load_review_papers_from_project(project_id: str) -> list[ReviewPaper]:
    index_path = reports_dir(project_id) / "index.json"
    if not index_path.exists():
        return []
    raw_index = _read_json(index_path)
    if not isinstance(raw_index, dict):
        return []

    papers: list[ReviewPaper] = []
    reports_root = index_path.parent
    for rel_path in raw_index.values():
        if not isinstance(rel_path, str):
            continue
        report_path = reports_root / rel_path
        if not report_path.exists():
            continue
        parsed = parse_review_report_markdown(
            report_path.read_text(encoding="utf-8"), rel_path
        )
        if parsed:
            papers.append(parsed)
    papers.sort(key=lambda paper: (paper.score is None, -(paper.score or 0.0), paper.title))
    return papers


def build_review_papers_from_query(query: str, limit: int) -> list[ReviewPaper]:
    papers: list[ReviewPaper] = []
    for result in search_library(query, limit=limit):
        papers.append(
            ReviewPaper(
                title=str(result["title"]),
                arxiv_url=str(result["arxiv_url"]),
                query=query,
                score=float(result["score"]) if result.get("score") is not None else None,
                abstract=str(result.get("abstract") or ""),
                matched_terms=tuple(str(x) for x in (result.get("matched_terms") or [])),
                source_report="search_library",
            )
        )
    return papers


def build_review_papers_from_results(
    query: str,
    results: list[dict[str, object]],
) -> list[ReviewPaper]:
    papers: list[ReviewPaper] = []
    for result in results:
        papers.append(
            ReviewPaper(
                title=str(result["title"]),
                arxiv_url=str(result["arxiv_url"]),
                query=query,
                score=float(result["score"]) if result.get("score") is not None else None,
                abstract=str(result.get("abstract") or ""),
                matched_terms=tuple(str(x) for x in (result.get("matched_terms") or [])),
                source_report="selected_results",
            )
        )
    return papers

