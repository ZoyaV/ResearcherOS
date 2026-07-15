from __future__ import annotations

import csv
import io

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.deps import workspace_relative
from api.schemas import LibraryDiscoverBody, LiteratureSearchBody, ReviewSetBody, TranslateToEnglishBody
from koi.application.project_views import project_to_client
from koi.services.literature import (
    LIBRARY_REQUIRED_FIELDS,
    LIBRARY_UPLOAD_PATH,
    bootstrap_library_from_arxiv,
    discover_library_with_agent,
    library_csv_exists,
    reset_library_cache,
    resolve_library_csv,
    review_card_id,
    review_project_description,
    review_project_title,
    search_arxiv_internet,
    search_library,
    translate_to_english,
)
from koi.services.literature import build_review_report
from koi.core.models import ExperimentCard, NodeType
from koi.adapters.repository import add_node, create_project, save_project, update_board
from koi.adapters.card_reports import write_report

router = APIRouter(tags=["library"])


@router.get("/library/status")
def get_library_status() -> dict[str, object]:
    exists = library_csv_exists()
    csv_path = None
    if exists:
        try:
            csv_path = workspace_relative(resolve_library_csv())
        except FileNotFoundError:
            exists = False
    return {
        "exists": exists,
        "csv_path": csv_path,
        "upload_path": workspace_relative(LIBRARY_UPLOAD_PATH),
    }


@router.post("/library/search")
def post_library_search(body: LiteratureSearchBody) -> dict[str, object]:
    query = body.query.strip()
    if not query:
        raise HTTPException(400, "Query must not be empty")
    try:
        library_csv = resolve_library_csv()
    except FileNotFoundError as e:
        raise HTTPException(
            503,
            "Library CSV was not found. Upload a CSV or use the separate library refresh button to rebuild the current database.",
        ) from e
    results = search_library(query, limit=body.limit)
    return {
        "query": query,
        "count": len(results),
        "results": results,
        "source": {
            "csv_path": workspace_relative(library_csv),
            "fields": ["no", "arxiv_url", "title", "authors", "abstract"],
            "required_fields": ["arxiv_url", "title"],
            "ranking_fields": ["title", "abstract"],
            "method": "hybrid title+abstract lexical ranking",
        },
    }


@router.post("/library/search-internet")
def post_library_search_internet(body: LiteratureSearchBody) -> dict[str, object]:
    query = body.query.strip()
    if not query:
        raise HTTPException(400, "Query must not be empty")
    results = search_arxiv_internet(query, limit=body.limit)
    return {
        "query": query,
        "count": len(results),
        "results": results,
        "papers": [
            {
                "title": result["title"],
                "arxiv_url": result["arxiv_url"],
                "authors": result.get("authors", ""),
                "abstract": result.get("abstract", ""),
            }
            for result in results
        ],
        "source": {
            "method": "arxiv_api",
            "url": "export.arxiv.org/api/query",
            "ranking_fields": ["title", "abstract"],
        },
    }


@router.post("/library/discover")
def post_library_discover(body: LibraryDiscoverBody) -> dict[str, object]:
    query = body.query.strip()
    if not query:
        raise HTTPException(400, "Query must not be empty")
    try:
        return discover_library_with_agent(query, limit=body.limit)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError:
        try:
            return bootstrap_library_from_arxiv(query, limit=body.limit)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(503, str(e)) from e


@router.post("/agent/translate-to-english")
def post_translate_to_english(body: TranslateToEnglishBody) -> dict[str, object]:
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "Text must not be empty")
    translated, backend = translate_to_english(text)
    if not translated:
        raise HTTPException(400, "Text must not be empty")
    return {
        "source_text": text,
        "translated_text": translated,
        "backend": backend,
    }


@router.post("/library/upload")
async def post_library_upload(file: UploadFile = File(...)) -> dict[str, object]:
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(400, "Library CSV must be UTF-8 encoded") from e

    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
    except csv.Error as e:
        raise HTTPException(400, f"Invalid CSV: {e}") from e

    fieldnames = tuple(reader.fieldnames or ())
    missing = [field for field in LIBRARY_REQUIRED_FIELDS if field not in fieldnames]
    if missing:
        raise HTTPException(
            400,
            f"Library CSV is missing required columns: {', '.join(missing)}",
        )

    row_count = 0
    try:
        for row_count, _row in enumerate(reader, start=1):
            pass
    except csv.Error as e:
        raise HTTPException(400, f"Invalid CSV row format: {e}") from e

    if row_count == 0:
        raise HTTPException(400, "Library CSV must contain at least one paper row")

    LIBRARY_UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIBRARY_UPLOAD_PATH.write_bytes(data)
    reset_library_cache()

    return {
        "ok": True,
        "csv_path": workspace_relative(LIBRARY_UPLOAD_PATH),
        "count": row_count,
        "fields": list(fieldnames),
        "required_fields": list(LIBRARY_REQUIRED_FIELDS),
        "filename": file.filename or LIBRARY_UPLOAD_PATH.name,
    }


@router.post("/library/review-set")
def post_library_review_set(body: ReviewSetBody) -> dict[str, object]:
    query = body.query.strip()
    if not query:
        raise HTTPException(400, "Query must not be empty")

    results = body.papers or search_library(query, limit=body.limit)
    if not results:
        raise HTTPException(400, "No ranked papers available for this query")

    project = create_project(review_project_title(query))
    project.description = review_project_description(query, len(results))
    root = next((n for n in project.nodes if n.node_type == NodeType.PROBLEM), None)
    if root is None:
        raise HTTPException(500, "Problem node missing in generated project")
    root.description = project.description
    save_project(project)

    cause = add_node(
        project,
        root.id,
        NodeType.CAUSE,
        "Candidate papers retrieved from the local library",
        "Auto-generated set of papers ranked against the current research question.",
    )
    evidence = add_node(
        project,
        cause.id,
        NodeType.CAUSE_EVIDENCE,
        "Evidence of relevance for the research question",
        f"Query: {query}",
    )
    method = add_node(
        project,
        evidence.id,
        NodeType.METHOD,
        "Screen, annotate, and shortlist the papers",
        "Each card corresponds to one ranked paper. Use the report to capture screening notes.",
    )

    board = next((b for b in project.boards if b.owner_node_id == method.id), None)
    if board is None:
        raise HTTPException(500, "Review board was not created")

    board.cards = [
        ExperimentCard(
            id=review_card_id(),
            board_id=board.id,
            column_id="backlog",
            title=str(result["title"]),
            description=str(result["arxiv_url"]),
        )
        for result in results
    ]
    update_board(project, board)

    for card, result in zip(board.cards, results):
        write_report(
            project,
            board.id,
            card.id,
            card.title,
            build_review_report(result, query),
        )

    return {
        "project": project_to_client(project),
        "query": query,
        "count": len(results),
    }
