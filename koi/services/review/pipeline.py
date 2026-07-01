from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from koi.adapters.agent_backends import any_agent_available
from koi.services.literature import _safe_filename, _slugify
from koi.services.review.artifacts import _load_existing_paper_answer_artifacts
from koi.services.review.analysis import (
    _cluster_paper_answers_heuristic,
    _generate_paper_answer_clusters_with_llm,
    _generate_paper_summary_with_llm,
    _generate_question_answer_from_abstract,
    _generate_question_answer_with_llm,
    build_cluster_report,
    build_paper_answer_cluster_report,
    build_paper_question_markdown,
    build_paper_summary_markdown,
    build_question_answer_index_markdown,
    classify_papers_to_clusters,
    propose_clusters,
)
from koi.services.review.arxiv import (
    extract_arxiv_html_text,
    extract_arxiv_id,
    extract_pdf_text,
    fetch_arxiv_html,
    fetch_arxiv_pdf,
    infer_year_from_arxiv_id,
)
from koi.services.review.models import (
    PAPER_REVIEW_BUNDLE_KIND,
    PaperAnswerArtifact,
    PaperAnswerCluster,
    PaperArtifact,
    PaperSummary,
    ProposedCluster,
    ReviewPaper,
)
from koi.services.review.papers import (
    build_review_papers_from_query,
    build_review_papers_from_results,
    load_review_papers_from_project,
)
from koi.services.review.storage import (
    _load_paper_answers_index,
    _load_top_level_index,
    _paper_answers_root,
    _paper_reviews_root,
    _save_paper_answers_index,
    _save_top_level_index,
    _write_universal_agent_bundle,
)
from koi.services.review.util import _default_progress

def run_review_agent(
    project_id: str,
    *,
    query: str | None = None,
    limit: int = 10,
    force_refresh: bool = False,
    download_pdfs: bool = True,
    selected_results: list[dict[str, object]] | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if progress:
        progress(f"Starting review agent for project '{project_id}'")
    if selected_results:
        if progress:
            progress(f"Building review set from {len(selected_results)} selected paper(s)")
        papers = build_review_papers_from_results(query or "", selected_results)
    elif query:
        if progress:
            progress(f"Ranking papers from query: {query}")
        papers = build_review_papers_from_query(query, limit=limit)
    else:
        if progress:
            progress(f"Loading existing review papers from project '{project_id}'")
        papers = load_review_papers_from_project(project_id)
        if limit > 0:
            papers = papers[:limit]
        if papers and not query:
            query = papers[0].query

    if not papers:
        raise ValueError("No review papers were found for this project or query.")
    if progress:
        progress(f"Preparing outputs for {len(papers)} paper(s)")

    root = _paper_reviews_root(project_id)
    root.mkdir(parents=True, exist_ok=True)
    folder_name = _slugify(query or f"{project_id}-review-agent", fallback="review-agent")
    review_dir = root / folder_name
    review_dir.mkdir(parents=True, exist_ok=True)
    agent_bundle_rel = f"agent_bundles/{PAPER_REVIEW_BUNDLE_KIND}/{project_id}/{folder_name}"
    pdf_dir = review_dir / "pdfs"
    text_dir = review_dir / "texts"
    summaries: dict[str, PaperSummary] = {}
    processed: list[tuple[int, ReviewPaper, Path | None, Path | None, Path | None, int, str]] = []
    artifacts: list[PaperArtifact] = []

    for rank, paper in enumerate(papers, start=1):
        if progress:
            progress(f"[{rank}/{len(papers)}] Processing '{paper.title}'")
        arxiv_id = extract_arxiv_id(paper.arxiv_url)
        html_path = review_dir / "htmls" / f"{arxiv_id}.html"
        pdf_path = pdf_dir / f"{arxiv_id}.pdf"
        text_path = text_dir / f"{arxiv_id}.txt"

        available_html: Path | None = None
        available_pdf: Path | None = None
        if download_pdfs:
            if progress:
                progress(f"[{rank}/{len(papers)}] Checking HTML cache for {arxiv_id}")
            available_html = fetch_arxiv_html(arxiv_id, html_path, force_refresh=force_refresh)
            if progress:
                progress(
                    f"[{rank}/{len(papers)}] HTML {'ready' if available_html else 'unavailable'} for {arxiv_id}"
                )
            if progress:
                progress(f"[{rank}/{len(papers)}] Checking PDF cache for {arxiv_id}")
            available_pdf = fetch_arxiv_pdf(arxiv_id, pdf_path, force_refresh=force_refresh)
            if progress:
                progress(
                    f"[{rank}/{len(papers)}] PDF {'ready' if available_pdf else 'unavailable'} for {arxiv_id}"
                )
        elif html_path.exists():
            available_html = html_path
            if pdf_path.exists():
                available_pdf = pdf_path
        elif pdf_path.exists():
            available_pdf = pdf_path

        full_text = ""
        if text_path.exists() and not force_refresh:
            if progress:
                progress(f"[{rank}/{len(papers)}] Reusing cached text for {arxiv_id}")
            full_text = text_path.read_text(encoding="utf-8")
        elif available_html is not None:
            if progress:
                progress(f"[{rank}/{len(papers)}] Extracting text from arXiv HTML for {arxiv_id}")
            full_text = extract_arxiv_html_text(available_html)
            if full_text:
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(full_text, encoding="utf-8")
                if progress:
                    progress(
                        f"[{rank}/{len(papers)}] Cached {len(full_text)} characters of text for {arxiv_id}"
                    )
            elif available_pdf is not None:
                if progress:
                    progress(f"[{rank}/{len(papers)}] HTML text was empty; falling back to PDF for {arxiv_id}")
                full_text = extract_pdf_text(available_pdf)
                if full_text:
                    text_path.parent.mkdir(parents=True, exist_ok=True)
                    text_path.write_text(full_text, encoding="utf-8")
                    if progress:
                        progress(
                            f"[{rank}/{len(papers)}] Cached {len(full_text)} characters of PDF text for {arxiv_id}"
                        )
                elif progress:
                    progress(f"[{rank}/{len(papers)}] No extractable text found for {arxiv_id}")
            elif progress:
                progress(f"[{rank}/{len(papers)}] No extractable HTML text found for {arxiv_id}")
        elif available_pdf is not None:
            if progress:
                progress(f"[{rank}/{len(papers)}] Extracting text from PDF for {arxiv_id}")
            full_text = extract_pdf_text(available_pdf)
            if full_text:
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(full_text, encoding="utf-8")
                if progress:
                    progress(
                        f"[{rank}/{len(papers)}] Cached {len(full_text)} characters of PDF text for {arxiv_id}"
                    )
            elif progress:
                progress(f"[{rank}/{len(papers)}] No extractable text found for {arxiv_id}")
        elif progress:
            progress(f"[{rank}/{len(papers)}] Falling back to abstract-only summary for {arxiv_id}")

        summary, summary_backend = _generate_paper_summary_with_llm(
            paper,
            full_text or paper.abstract or paper.title,
            used_full_text=bool(full_text),
        )
        if summary is None:
            raise RuntimeError(
                f"LLM summary generation failed for '{paper.title}'. No heuristic fallback is enabled."
            )
        summaries[paper.title] = summary
        processed.append(
            (
                rank,
                paper,
                available_html,
                available_pdf,
                text_path if text_path.exists() else None,
                len(full_text),
                arxiv_id,
                summary_backend,
            )
        )
        if progress:
            progress(
                f"[{rank}/{len(papers)}] Summary prepared; extracted terms: {', '.join(summary.signature_terms[:4]) or 'n/a'}"
            )

    if progress:
        progress("Proposing clusters from the full set of summaries")
    clusters = propose_clusters(query or "", papers, summaries)
    assignments = classify_papers_to_clusters(papers, summaries, clusters)
    if progress:
        progress(f"Proposed {len(clusters)} cluster(s); writing per-paper summaries with assignments")

    for rank, paper, available_html, available_pdf, cached_text_path, extracted_text_chars, arxiv_id, summary_backend in processed:
        summary = summaries[paper.title]
        summary_filename = f"{rank:02d}_{_safe_filename(paper.title, fallback=f'paper_{rank:02d}')}"
        summary_path = review_dir / summary_filename
        cluster = assignments[paper.title]
        cluster_assignment_rationale = _assignment_rationale(paper, summary, cluster)
        summary_path.write_text(
            build_paper_summary_markdown(
                paper,
                summary,
                rank=rank,
                html_path=available_html,
                pdf_path=available_pdf,
                text_path=cached_text_path,
                extracted_text_chars=extracted_text_chars,
                summary_backend=summary_backend,
                cluster=cluster,
                cluster_assignment_rationale=cluster_assignment_rationale,
            ),
            encoding="utf-8",
        )
        if progress:
            progress(
                f"[{rank}/{len(papers)}] Wrote summary '{summary_filename}' in cluster '{cluster.label}'"
            )

        artifacts.append(
            PaperArtifact(
                rank=rank,
                title=paper.title,
                arxiv_url=paper.arxiv_url,
                arxiv_id=arxiv_id,
                year=infer_year_from_arxiv_id(arxiv_id),
                source_report=paper.source_report,
                summary_path=summary_filename,
                html_path=str(available_html.relative_to(review_dir)) if available_html else None,
                pdf_path=str(available_pdf.relative_to(review_dir)) if available_pdf else None,
                text_path=str(cached_text_path.relative_to(review_dir)) if cached_text_path else None,
                extracted_text_chars=extracted_text_chars,
                used_full_text=bool(extracted_text_chars),
                summary_backend=summary_backend,
                cluster_key=cluster.key,
                cluster_label=cluster.label,
                query_answer=summary.query_answer,
                answer_strategy_key=summary.answer_strategy_key,
                answer_strategy_label=summary.answer_strategy_label,
                answer_evidence=summary.answer_evidence,
                assignment_rationale=cluster_assignment_rationale,
            )
        )

    cluster_report_path = review_dir / "cluster_directions.md"
    if progress:
        progress("Writing cluster synthesis report")
    cluster_report_path.write_text(
        build_cluster_report(query or "", clusters, artifacts, summaries),
        encoding="utf-8",
    )

    manifest = {
        "query": query or "",
        "project_id": project_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(artifacts),
        "download_pdfs": download_pdfs,
        "clusters": [asdict(cluster) for cluster in clusters],
        "papers": [asdict(artifact) for artifact in artifacts],
        "cluster_report": cluster_report_path.name,
        "agent_bundle": f"../../../{agent_bundle_rel}",
    }
    (review_dir / "index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if progress:
        progress("Writing universal agent bundle")
    _write_universal_agent_bundle(
        review_dir,
        project_id=project_id,
        bundle_name=folder_name,
        query=query or "",
        manifest=manifest,
    )

    top_index = [row for row in _load_top_level_index(project_id) if row.get("folder") != review_dir.name]
    top_index.append(
        {
            "folder": review_dir.name,
            "query": query or "",
            "created_at": manifest["created_at"],
            "count": len(artifacts),
            "path": f"paper_reviews/{review_dir.name}",
            "cluster_report": f"paper_reviews/{review_dir.name}/{cluster_report_path.name}",
            "agent_bundle": agent_bundle_rel,
        }
    )
    _save_top_level_index(project_id, top_index)
    if progress:
        progress(f"Done. Outputs available in '{review_dir}'")

    return {
        "project_id": project_id,
        "query": query or "",
        "count": len(artifacts),
        "folder": review_dir.name,
        "path": f"paper_reviews/{review_dir.name}",
        "cluster_report": f"paper_reviews/{review_dir.name}/{cluster_report_path.name}",
        "agent_bundle": agent_bundle_rel,
        "clusters": [asdict(cluster) for cluster in clusters],
        "papers": [asdict(artifact) for artifact in artifacts],
    }


def run_paper_question_agent(
    project_id: str,
    *,
    question: str,
    limit: int = 10,
    force_refresh: bool = False,
    download_pdfs: bool = True,
    selected_results: list[dict[str, object]] | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("Question must not be empty.")

    if selected_results:
        if progress:
            progress(f"Building paper QA set from {len(selected_results)} selected paper(s)")
        papers = build_review_papers_from_results(normalized_question, selected_results)
    else:
        if progress:
            progress(f"Ranking papers from question: {normalized_question}")
        papers = build_review_papers_from_query(normalized_question, limit=limit)

    if not papers:
        raise ValueError("No papers were found for this question.")

    agent_ready = any_agent_available()
    if not agent_ready:
        download_pdfs = False
        if progress:
            progress(
                "No LLM agent backend is configured; using abstract-based answers and heuristic clustering."
            )

    if progress:
        progress(f"Preparing question-answer outputs for {len(papers)} paper(s)")

    root = _paper_answers_root(project_id)
    root.mkdir(parents=True, exist_ok=True)
    folder_name = _slugify(normalized_question, fallback="paper-question-answer")
    answer_dir = root / folder_name
    answer_dir.mkdir(parents=True, exist_ok=True)
    html_dir = answer_dir / "htmls"
    pdf_dir = answer_dir / "pdfs"
    text_dir = answer_dir / "texts"
    artifacts: list[PaperAnswerArtifact] = []
    existing_artifacts = {} if force_refresh else _load_existing_paper_answer_artifacts(answer_dir)

    for rank, paper in enumerate(papers, start=1):
        existing_artifact = existing_artifacts.get(paper.title)
        if existing_artifact is not None:
            if progress:
                progress(f"[{rank}/{len(papers)}] Reusing existing answer for '{paper.title}' and skipping regeneration")
            artifacts.append(
                replace(
                    existing_artifact,
                    rank=rank,
                    source_report=paper.source_report,
                )
            )
            continue
        if progress:
            progress(f"[{rank}/{len(papers)}] Answering question for '{paper.title}'")
        arxiv_id = extract_arxiv_id(paper.arxiv_url)
        html_path = html_dir / f"{arxiv_id}.html"
        pdf_path = pdf_dir / f"{arxiv_id}.pdf"
        text_path = text_dir / f"{arxiv_id}.txt"

        available_html: Path | None = None
        available_pdf: Path | None = None
        if download_pdfs:
            available_html = fetch_arxiv_html(arxiv_id, html_path, force_refresh=force_refresh)
            available_pdf = fetch_arxiv_pdf(arxiv_id, pdf_path, force_refresh=force_refresh)
        elif html_path.exists():
            available_html = html_path
            if pdf_path.exists():
                available_pdf = pdf_path
        elif pdf_path.exists():
            available_pdf = pdf_path

        full_text = ""
        if text_path.exists() and not force_refresh:
            full_text = text_path.read_text(encoding="utf-8")
        elif available_html is not None:
            full_text = extract_arxiv_html_text(available_html)
            if not full_text and available_pdf is not None:
                full_text = extract_pdf_text(available_pdf)
            if full_text:
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(full_text, encoding="utf-8")
        elif available_pdf is not None:
            full_text = extract_pdf_text(available_pdf)
            if full_text:
                text_path.parent.mkdir(parents=True, exist_ok=True)
                text_path.write_text(full_text, encoding="utf-8")

        source_text = full_text or paper.abstract or paper.title
        short_answer: str | None
        comprehensive_answer: str | None
        evidence: tuple[str, ...]
        limitations: str | None
        backend: str | None
        answer_source = "llm_agent"
        if agent_ready:
            short_answer, comprehensive_answer, evidence, limitations, backend = (
                _generate_question_answer_with_llm(
                    paper,
                    normalized_question,
                    source_text,
                    used_full_text=bool(full_text),
                )
            )
        else:
            short_answer, comprehensive_answer, evidence, limitations, backend = (
                _generate_question_answer_from_abstract(
                    paper,
                    normalized_question,
                    source_text,
                    used_full_text=bool(full_text),
                )
            )
            answer_source = "abstract_heuristic"
        if not short_answer or not comprehensive_answer or not limitations:
            (
                short_answer,
                comprehensive_answer,
                evidence,
                limitations,
                backend,
            ) = _generate_question_answer_from_abstract(
                paper,
                normalized_question,
                source_text,
                used_full_text=bool(full_text),
            )
            answer_source = "abstract_heuristic"

        answer_filename = f"{rank:02d}_{_safe_filename(paper.title, fallback=f'paper_{rank:02d}')}"
        answer_path = answer_dir / answer_filename
        answer_path.write_text(
            build_paper_question_markdown(
                paper,
                question=normalized_question,
                rank=rank,
                html_path=available_html,
                pdf_path=available_pdf,
                text_path=text_path if text_path.exists() else None,
                extracted_text_chars=len(full_text),
                answer_backend=backend,
                answer_source=answer_source,
                short_answer=short_answer,
                comprehensive_answer=comprehensive_answer,
                evidence=evidence,
                limitations=limitations,
            ),
            encoding="utf-8",
        )

        artifacts.append(
            PaperAnswerArtifact(
                rank=rank,
                title=paper.title,
                arxiv_url=paper.arxiv_url,
                arxiv_id=arxiv_id,
                year=infer_year_from_arxiv_id(arxiv_id),
                source_report=paper.source_report,
                answer_path=answer_filename,
                html_path=str(available_html.relative_to(answer_dir)) if available_html else None,
                pdf_path=str(available_pdf.relative_to(answer_dir)) if available_pdf else None,
                text_path=str(text_path.relative_to(answer_dir)) if text_path.exists() else None,
                extracted_text_chars=len(full_text),
                used_full_text=bool(full_text),
                answer_backend=backend,
                answer_source=answer_source,
                short_answer=short_answer,
                comprehensive_answer=comprehensive_answer,
                evidence=evidence,
                limitations=limitations,
            )
        )

    answer_documents = [
        (
            artifact.title,
            (answer_dir / artifact.answer_path).read_text(encoding="utf-8"),
        )
        for artifact in artifacts
    ]
    clusters, cluster_backend = _generate_paper_answer_clusters_with_llm(
        normalized_question,
        answer_documents,
    )
    if not clusters:
        clusters = _cluster_paper_answers_heuristic(normalized_question, artifacts)
        cluster_backend = "abstract_heuristic"
    if not clusters:
        raise RuntimeError(
            f"Answer clustering failed for question '{normalized_question}'."
        )

    cluster_by_title: dict[str, PaperAnswerCluster] = {}
    for cluster in clusters:
        for title in cluster.paper_titles:
            cluster_by_title[title] = cluster

    artifacts = [
        replace(
            artifact,
            cluster_key=cluster_by_title[artifact.title].key,
            cluster_label=cluster_by_title[artifact.title].label,
            cluster_rationale=cluster_by_title[artifact.title].rationale,
        )
        for artifact in artifacts
    ]

    cluster_report_path = answer_dir / "answer_clusters.md"
    cluster_report_path.write_text(
        build_paper_answer_cluster_report(
            normalized_question,
            artifacts,
            clusters,
            cluster_backend=cluster_backend,
        ),
        encoding="utf-8",
    )

    index_md_path = answer_dir / "answers_index.md"
    index_md_path.write_text(
        build_question_answer_index_markdown(
            normalized_question,
            artifacts,
            clusters=clusters,
            cluster_report_path=cluster_report_path.name,
        ),
        encoding="utf-8",
    )

    manifest = {
        "question": normalized_question,
        "project_id": project_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(artifacts),
        "download_pdfs": download_pdfs,
        "index_markdown": index_md_path.name,
        "cluster_report": cluster_report_path.name,
        "cluster_backend": cluster_backend,
        "clusters": [asdict(cluster) for cluster in clusters],
        "papers": [asdict(artifact) for artifact in artifacts],
    }
    (answer_dir / "index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    top_index = [
        row for row in _load_paper_answers_index(project_id) if row.get("folder") != answer_dir.name
    ]
    top_index.append(
        {
            "folder": answer_dir.name,
            "question": normalized_question,
            "created_at": manifest["created_at"],
            "count": len(artifacts),
            "path": f"paper_answers/{answer_dir.name}",
            "index_markdown": f"paper_answers/{answer_dir.name}/{index_md_path.name}",
            "cluster_report": f"paper_answers/{answer_dir.name}/{cluster_report_path.name}",
        }
    )
    _save_paper_answers_index(project_id, top_index)

    return {
        "project_id": project_id,
        "question": normalized_question,
        "count": len(artifacts),
        "folder": answer_dir.name,
        "path": f"paper_answers/{answer_dir.name}",
        "index_markdown": f"paper_answers/{answer_dir.name}/{index_md_path.name}",
        "cluster_report": f"paper_answers/{answer_dir.name}/{cluster_report_path.name}",
        "cluster_backend": cluster_backend,
        "clusters": [asdict(cluster) for cluster in clusters],
        "papers": [asdict(artifact) for artifact in artifacts],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate arXiv-backed paper review summaries and cluster directions.")
    parser.add_argument("project_id", help="KOI project id")
    parser.add_argument("--query", default=None, help="Optional research question to rank papers from the local library")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of papers")
    parser.add_argument("--refresh", action="store_true", help="Re-download PDFs and re-extract text")
    parser.add_argument(
        "--no-pdf-download",
        action="store_true",
        help="Skip PDF download and summarize from existing text cache or abstracts only",
    )
    args = parser.parse_args(argv)

    result = run_review_agent(
        args.project_id,
        query=args.query,
        limit=args.limit,
        force_refresh=args.refresh,
        download_pdfs=not args.no_pdf_download,
        progress=_default_progress,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
