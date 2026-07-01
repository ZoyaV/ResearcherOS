from __future__ import annotations

import json
from pathlib import Path

from koi.services.review.analysis import _normalize_llm_evidence
from koi.services.review.models import PaperAnswerArtifact
from koi.services.review.util import _normalize_text, _read_json


def _paper_answer_artifact_from_dict(data: dict[str, object]) -> PaperAnswerArtifact | None:
    title = _normalize_text(str(data.get("title") or ""))
    arxiv_url = _normalize_text(str(data.get("arxiv_url") or ""))
    arxiv_id = _normalize_text(str(data.get("arxiv_id") or ""))
    source_report = _normalize_text(str(data.get("source_report") or ""))
    answer_path = _normalize_text(str(data.get("answer_path") or ""))
    short_answer = str(data.get("short_answer") or "").strip()
    comprehensive_answer = str(data.get("comprehensive_answer") or "").strip()
    limitations = str(data.get("limitations") or "").strip()
    if not all([title, arxiv_url, arxiv_id, source_report, answer_path, short_answer, comprehensive_answer, limitations]):
        return None
    return PaperAnswerArtifact(
        rank=int(data.get("rank") or 0),
        title=title,
        arxiv_url=arxiv_url,
        arxiv_id=arxiv_id,
        year=int(data["year"]) if isinstance(data.get("year"), int) else None,
        source_report=source_report,
        answer_path=answer_path,
        html_path=str(data["html_path"]) if data.get("html_path") is not None else None,
        pdf_path=str(data["pdf_path"]) if data.get("pdf_path") is not None else None,
        text_path=str(data["text_path"]) if data.get("text_path") is not None else None,
        extracted_text_chars=int(data.get("extracted_text_chars") or 0),
        used_full_text=bool(data.get("used_full_text")),
        answer_backend=str(data["answer_backend"]) if data.get("answer_backend") is not None else None,
        answer_source=_normalize_text(str(data.get("answer_source") or "llm_agent")),
        short_answer=short_answer,
        comprehensive_answer=comprehensive_answer,
        evidence=_normalize_llm_evidence(data.get("evidence"), limit=8),
        limitations=limitations,
        cluster_key=str(data["cluster_key"]) if data.get("cluster_key") is not None else None,
        cluster_label=str(data["cluster_label"]) if data.get("cluster_label") is not None else None,
        cluster_rationale=str(data["cluster_rationale"]) if data.get("cluster_rationale") is not None else None,
    )


def _load_existing_paper_answer_artifacts(answer_dir: Path) -> dict[str, PaperAnswerArtifact]:
    index_path = answer_dir / "index.json"
    if not index_path.exists():
        return {}
    try:
        payload = _read_json(index_path)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    papers = payload.get("papers")
    if not isinstance(papers, list):
        return {}
    loaded: dict[str, PaperAnswerArtifact] = {}
    for item in papers:
        if not isinstance(item, dict):
            continue
        artifact = _paper_answer_artifact_from_dict(item)
        if artifact is None:
            continue
        if not (answer_dir / artifact.answer_path).exists():
            continue
        loaded[artifact.title] = artifact
    return loaded
