"""Separate presentation runs built from completed article morphology graphs."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from koi.adapters.workspace import get_workspace
from koi.literature import morphology as morphology_service
from koi.literature.morphology_presentation_validate import (
    validate_presentation,
    validate_presentation_critique,
)


SKILL_PATH = ".cursor/skills/article-morphology-presentation/SKILL.md"
PRESENTATION_FILENAME = "presentation.json"
CRITIQUE_FILENAME = "presentation_critique.json"
REQUIRED_ARTIFACTS = (PRESENTATION_FILENAME, CRITIQUE_FILENAME)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _display_path(path: Path) -> str:
    try:
        return get_workspace().relative_to_engine(path)
    except ValueError:
        return str(path)


def presentations_dir(project_id: str, morphology_run_id: str) -> Path:
    return (
        morphology_service.morphology_dir(project_id)
        / morphology_run_id
        / "presentations"
    )


def make_presentation_run_id(*, when: datetime | None = None) -> str:
    stamp = (when or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S")
    return f"presentation_{stamp}"


def allocate_presentation_run_id(project_id: str, morphology_run_id: str) -> str:
    root = presentations_dir(project_id, morphology_run_id)
    base = make_presentation_run_id()
    if not (root / base).exists():
        return base
    for index in range(2, 100):
        candidate = f"{base}_{index}"
        if not (root / candidate).exists():
            return candidate
    raise RuntimeError("Could not allocate a presentation run id.")


def _load_index(project_id: str, morphology_run_id: str) -> list[dict[str, object]]:
    payload = _read_json(presentations_dir(project_id, morphology_run_id) / "index.json")
    return payload if isinstance(payload, list) else []


def _save_index(
    project_id: str,
    morphology_run_id: str,
    rows: list[dict[str, object]],
) -> None:
    _write_json(presentations_dir(project_id, morphology_run_id) / "index.json", rows)


def _upsert_index(
    project_id: str,
    morphology_run_id: str,
    row: dict[str, object],
) -> None:
    run_id = str(row.get("run_id") or "")
    rows = [
        existing
        for existing in _load_index(project_id, morphology_run_id)
        if isinstance(existing, dict) and str(existing.get("run_id") or "") != run_id
    ]
    rows.append(row)
    _save_index(project_id, morphology_run_id, rows)


def _parent_inputs(
    project_id: str,
    morphology_run_id: str,
) -> tuple[Path, dict[str, Any], dict[str, Any], Path]:
    parent = morphology_service.morphology_dir(project_id) / morphology_run_id
    morphology = _read_json(parent / morphology_service.MORPHOLOGY_FILENAME)
    math_analysis = _read_json(parent / morphology_service.MATH_ANALYSIS_FILENAME)
    source = morphology_service.resolve_article_source(parent)
    if not isinstance(morphology, dict):
        raise ValueError("The morphology graph is not ready.")
    if not isinstance(math_analysis, dict):
        raise ValueError("Mathematical lessons are not ready.")
    if not source or source.get("kind") != "html":
        raise ValueError("The saved article HTML is required for figures and tables.")
    source_path = source.get("path")
    if not isinstance(source_path, Path):
        raise ValueError("The saved article HTML could not be resolved.")
    return parent, morphology, math_analysis, source_path


def compose_presentation_chat_prompt(
    *,
    morphology_run_id: str,
    presentation_run_id: str,
    parent_dir: Path,
    article_path: Path,
    run_dir: Path,
) -> str:
    graph_path = _display_path(parent_dir / morphology_service.MORPHOLOGY_FILENAME)
    math_path = _display_path(parent_dir / morphology_service.MATH_ANALYSIS_FILENAME)
    article_rel = _display_path(article_path)
    output_path = _display_path(run_dir)
    return f"""Use the `article-morphology-presentation` skill ({SKILL_PATH}). Create one
presentation from the completed morphology graph. Read the graph, mathematical lessons,
and saved article. Do not rerun morphology or modify the graph nodes.

Cover every node in article order. Create one main slide for each node. Place any supporting
slides for mathematics, algorithms, figures, or result tables directly after the corresponding
main slide.

## Inputs
- Morphology graph: `{graph_path}`
- Mathematical lessons: `{math_path}`
- Saved article: `{article_rel}`
- morphology_run_id: `{morphology_run_id}`
- presentation_run_id: `{presentation_run_id}`

## Output
- Directory: `{output_path}`
- Write `{PRESENTATION_FILENAME}`.
- Write `{CRITIQUE_FILENAME}` after rendering every slide at 16:9.
- Validate with `koi.literature.morphology_presentation_validate`.

Method nodes require mathematics or an algorithm slide. Result nodes require a grounded
table slice whose highlighted values support the node claim. Do not invent nodes, equations,
figures, table values, captions, or source anchors.

Finish only after deterministic validation succeeds and the readability review approves every
slide.
""".strip()


def stage_morphology_presentation(
    project_id: str,
    morphology_run_id: str,
) -> dict[str, object]:
    morphology_run_id = str(morphology_run_id or "").strip()
    if not morphology_run_id:
        raise ValueError("Morphology run id is required.")
    parent, morphology, math_analysis, article_path = _parent_inputs(
        project_id, morphology_run_id
    )
    presentation_run_id = allocate_presentation_run_id(project_id, morphology_run_id)
    run_dir = presentations_dir(project_id, morphology_run_id) / presentation_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    created_at = _now_iso()
    _write_json(
        run_dir / "input.json",
        {
            "run_id": presentation_run_id,
            "morphology_run_id": morphology_run_id,
            "created_at": created_at,
            "status": "staged",
            "required_artifacts": list(REQUIRED_ARTIFACTS),
            "sources": {
                "morphology": _display_path(
                    parent / morphology_service.MORPHOLOGY_FILENAME
                ),
                "math_analysis": _display_path(
                    parent / morphology_service.MATH_ANALYSIS_FILENAME
                ),
                "article_html": _display_path(article_path),
            },
            "source_counts": {
                "nodes": len(morphology.get("nodes") or []),
                "math_occurrences": math_analysis.get("source_math_count") or 0,
            },
        },
    )
    prompt = compose_presentation_chat_prompt(
        morphology_run_id=morphology_run_id,
        presentation_run_id=presentation_run_id,
        parent_dir=parent,
        article_path=article_path,
        run_dir=run_dir,
    )
    (run_dir / "PROMPT.md").write_text(prompt + "\n", encoding="utf-8")
    history_row = {
        "run_id": presentation_run_id,
        "morphology_run_id": morphology_run_id,
        "created_at": created_at,
        "status": "staged",
        "backend": "cursor_chat",
        "path": (
            f"paper_morphology/{morphology_run_id}/presentations/"
            f"{presentation_run_id}"
        ),
    }
    _upsert_index(project_id, morphology_run_id, history_row)
    return {
        **history_row,
        "input_path": _display_path(run_dir / "input.json"),
        "output_dir": _display_path(run_dir),
        "prompt": prompt,
        "cursor_message": prompt,
    }


def _validation_errors(
    project_id: str,
    morphology_run_id: str,
    run_dir: Path,
) -> list[str]:
    presentation = _read_json(run_dir / PRESENTATION_FILENAME)
    critique = _read_json(run_dir / CRITIQUE_FILENAME)
    if not isinstance(presentation, dict) or not isinstance(critique, dict):
        return []
    _, morphology, math_analysis, article_path = _parent_inputs(
        project_id, morphology_run_id
    )
    article_html = article_path.read_text(encoding="utf-8", errors="replace")
    return [
        *validate_presentation(
            presentation,
            morphology,
            math_analysis,
            article_html,
        ),
        *validate_presentation_critique(critique, presentation),
    ]


def _run_status(
    project_id: str,
    morphology_run_id: str,
    run_dir: Path,
) -> tuple[str, list[str]]:
    if not all((run_dir / name).is_file() for name in REQUIRED_ARTIFACTS):
        return "staged", []
    errors = _validation_errors(project_id, morphology_run_id, run_dir)
    return ("invalid", errors) if errors else ("ready", [])


def list_presentation_runs(
    project_id: str,
    morphology_run_id: str,
) -> list[dict[str, object]]:
    root = presentations_dir(project_id, morphology_run_id)
    rows: list[dict[str, object]] = []
    for row in _load_index(project_id, morphology_run_id):
        if not isinstance(row, dict):
            continue
        run_id = str(row.get("run_id") or "").strip()
        if not run_id:
            continue
        status, errors = _run_status(
            project_id,
            morphology_run_id,
            root / run_id,
        )
        normalized = dict(row)
        normalized["status"] = status
        normalized["validation_errors"] = errors
        rows.append(normalized)
    return sorted(
        rows,
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )


def load_presentation_run(
    project_id: str,
    morphology_run_id: str,
    presentation_run_id: str,
) -> dict[str, object] | None:
    presentation_run_id = str(presentation_run_id or "").strip()
    if not presentation_run_id:
        return None
    run_dir = (
        presentations_dir(project_id, morphology_run_id) / presentation_run_id
    )
    staged = _read_json(run_dir / "input.json")
    if not isinstance(staged, dict):
        return None
    status, errors = _run_status(
        project_id,
        morphology_run_id,
        run_dir,
    )
    payload: dict[str, object] = {
        "run_id": presentation_run_id,
        "morphology_run_id": morphology_run_id,
        "created_at": str(staged.get("created_at") or ""),
        "status": status,
        "validation_errors": errors,
    }
    presentation = _read_json(run_dir / PRESENTATION_FILENAME)
    if isinstance(presentation, dict):
        payload["presentation"] = presentation
    critique = _read_json(run_dir / CRITIQUE_FILENAME)
    if isinstance(critique, dict):
        payload["critique"] = critique
    prompt_path = run_dir / "PROMPT.md"
    if prompt_path.is_file():
        prompt = prompt_path.read_text(encoding="utf-8")
        payload["prompt"] = prompt
        payload["cursor_message"] = prompt
    return payload


def latest_presentation_run(
    project_id: str,
    morphology_run_id: str,
) -> dict[str, object] | None:
    runs = list_presentation_runs(project_id, morphology_run_id)
    if not runs:
        return None
    preferred = next(
        (row for row in runs if row.get("status") == "ready"),
        None,
    ) or next(
        (row for row in runs if row.get("status") == "invalid"),
        None,
    ) or runs[0]
    return load_presentation_run(
        project_id,
        morphology_run_id,
        str(preferred["run_id"]),
    )


def delete_presentation_run(
    project_id: str,
    morphology_run_id: str,
    presentation_run_id: str,
) -> dict[str, object]:
    presentation_run_id = str(presentation_run_id or "").strip()
    if not presentation_run_id:
        raise ValueError("Presentation run id is required.")
    run_dir = (
        presentations_dir(project_id, morphology_run_id) / presentation_run_id
    )
    if not run_dir.is_dir():
        raise LookupError(f"Presentation run '{presentation_run_id}' was not found.")
    shutil.rmtree(run_dir)
    _save_index(
        project_id,
        morphology_run_id,
        [
            row
            for row in _load_index(project_id, morphology_run_id)
            if not isinstance(row, dict)
            or str(row.get("run_id") or "") != presentation_run_id
        ],
    )
    return {
        "ok": True,
        "run_id": presentation_run_id,
        "removed": "run_dir",
    }


__all__ = [
    "CRITIQUE_FILENAME",
    "PRESENTATION_FILENAME",
    "delete_presentation_run",
    "latest_presentation_run",
    "list_presentation_runs",
    "load_presentation_run",
    "stage_morphology_presentation",
]
