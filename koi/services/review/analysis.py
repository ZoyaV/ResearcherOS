from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from koi.adapters.agent_backends import any_agent_available, run_agent
from koi.adapters.paths import agent_bundles_dir, paper_answers_dir, paper_reviews_dir
from koi.adapters.settings_store import load_env_file
from koi.adapters.workspace import get_workspace
from koi.services.literature import _safe_filename, _slugify
from koi.services.review.arxiv import (
    extract_arxiv_html_text,
    extract_arxiv_id,
    extract_pdf_text,
    fetch_arxiv_html,
    fetch_arxiv_pdf,
    infer_year_from_arxiv_id,
)
from koi.services.review.models import (
    ANSWER_STRATEGIES,
    ANSWER_STRATEGY_BY_KEY,
    AnswerStrategy,
    PaperAnswerArtifact,
    PaperAnswerCluster,
    PaperArtifact,
    PaperSummary,
    ProposedCluster,
    ReviewPaper,
    UNIVERSAL_AGENT_SPEC,
)
from koi.services.review.papers import (
    build_review_papers_from_query,
    build_review_papers_from_results,
    load_review_papers_from_project,
    parse_review_report_markdown,
)
from koi.services.review.util import (
    _default_progress,
    _normalize_text,
    _read_json,
    _tokenize,
)

def _unique_in_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


CLUSTER_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "can", "could",
    "did", "do", "does", "for", "from", "had", "has", "have", "how", "however", "in",
    "into", "is", "it", "its", "just", "may", "might", "must", "new", "no", "not", "of",
    "on", "one", "or", "our", "paper", "present", "propose", "show", "shows", "such",
    "than", "that", "the", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "to", "two", "using", "was", "we", "well", "were", "which",
    "while", "will", "with", "would",
}


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token
        for token in _tokenize(text)
        if token not in CLUSTER_STOPWORDS and len(token) > 2
    }


def _paper_summary_text(
    paper: ReviewPaper,
    summary: PaperSummary,
    *,
    include_title: bool = False,
) -> str:
    return " ".join(
        [part for part in [
            paper.title if include_title else "",
            paper.abstract,
            summary.core_idea,
            summary.representation_of_dynamics,
            summary.evidence,
            summary.usefulness,
        ] if part]
    )


def _distinct_sentences(sentences: list[str], limit: int = 3) -> tuple[str, ...]:
    seen: set[str] = set()
    picked: list[str] = []
    for sentence in sentences:
        normalized = _normalize_text(sentence)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        picked.append(normalized)
        if len(picked) >= limit:
            break
    return tuple(picked)


def _quote_excerpt(text: str, *, limit: int = 180) -> str:
    compact = _normalize_text(text)
    if len(compact) <= limit:
        return compact
    clipped = compact[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{clipped}..."


def _strip_code_fences(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped.startswith("```"):
        return stripped
    stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_json_object(text: str) -> dict[str, object] | None:
    stripped = _strip_code_fences(text)
    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _normalize_llm_evidence(value: object, *, limit: int = 8) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    snippets: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        compact = _normalize_text(item)
        if compact:
            snippets.append(compact)
    return _distinct_sentences(snippets, limit=limit)


def _normalize_llm_terms(value: object, *, limit: int = 8) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    terms: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        compact = _normalize_text(item)
        if compact:
            terms.append(compact)
    return tuple(_unique_in_order(terms)[:limit])


def _strategy_catalog_text() -> str:
    lines = []
    for strategy in ANSWER_STRATEGIES:
        lines.append(f"- {strategy.key}: {strategy.label} — {strategy.answer_hint}")
    return "\n".join(lines)


def _normalize_strategy_key(value: object) -> str | None:
    key = _normalize_text(str(value or "")).lower().replace(" ", "_").replace("-", "_")
    return key if key in ANSWER_STRATEGY_BY_KEY else None


def _build_paper_summary_prompt(
    paper: ReviewPaper,
    source_text: str,
    *,
    used_full_text: bool,
) -> str:
    source_label = "full extracted paper text" if used_full_text else "abstract or sparse extracted text"
    return (
        "You are analyzing one paper for a literature review.\n"
        "Answer ONLY from the provided paper text. Do not infer missing details from background knowledge.\n"
        "If the paper does not directly answer the query, say so explicitly.\n"
        "Return valid JSON only.\n\n"
        "Choose exactly one answer strategy key from this list:\n"
        f"{_strategy_catalog_text()}\n\n"
        "Return JSON with this exact schema:\n"
        "{\n"
        '  "core_idea": string,\n'
        '  "representation_of_dynamics": string,\n'
        '  "query_answer": string,\n'
        '  "answer_strategy_key": string,\n'
        '  "answer_evidence": [string],\n'
        '  "evidence": string,\n'
        '  "usefulness": string,\n'
        '  "limitations": string,\n'
        '  "signature_terms": [string],\n'
        '  "citation_sentences": [string]\n'
        "}\n\n"
        "Field rules:\n"
        "- core_idea: 1-3 sentences.\n"
        "- representation_of_dynamics: describe exactly how the paper represents dynamics, or state clearly that it does not directly do so.\n"
        "- query_answer: answer the review question directly.\n"
        "- answer_strategy_key: one of the allowed keys above.\n"
        "- answer_evidence: 1-4 verbatim snippets from the paper supporting the answer.\n"
        "- evidence: concise note about experimental evidence/setup directly supported by source.\n"
        "- usefulness: why this paper matters for the question.\n"
        "- limitations: one concise caution grounded in source coverage.\n"
        "- signature_terms: 3-8 short phrases summarizing the paper's answer.\n"
        "- citation_sentences: 1-4 verbatim supporting snippets.\n\n"
        f"Question: {paper.query or 'n/a'}\n"
        f"Paper title: {paper.title}\n"
        f"ArXiv URL: {paper.arxiv_url}\n"
        f"Source quality: {source_label}\n\n"
        "Paper abstract:\n"
        f"{paper.abstract or 'No abstract available.'}\n\n"
        "Paper text:\n"
        f"{source_text}\n"
    )


def _generate_paper_summary_with_llm(
    paper: ReviewPaper,
    source_text: str,
    *,
    used_full_text: bool,
) -> tuple[PaperSummary | None, str | None]:
    load_env_file()
    prompt = _build_paper_summary_prompt(paper, source_text, used_full_text=used_full_text)
    text, backend = run_agent(prompt, cwd=get_workspace().agent_cwd())
    if not text:
        return None, backend
    payload = _extract_json_object(text)
    if not payload:
        return None, backend

    strategy_key = _normalize_strategy_key(payload.get("answer_strategy_key"))
    if not strategy_key:
        return None, backend
    strategy = ANSWER_STRATEGY_BY_KEY[strategy_key]

    core_idea = str(payload.get("core_idea") or "").strip()
    representation = str(payload.get("representation_of_dynamics") or "").strip()
    query_answer = str(payload.get("query_answer") or "").strip()
    evidence = str(payload.get("evidence") or "").strip()
    usefulness = str(payload.get("usefulness") or "").strip()
    limitations = str(payload.get("limitations") or "").strip()
    answer_evidence = _normalize_llm_evidence(payload.get("answer_evidence"), limit=4)
    signature_terms = _normalize_llm_terms(payload.get("signature_terms"), limit=8)
    citation_sentences = _normalize_llm_evidence(payload.get("citation_sentences"), limit=4)
    if not all([core_idea, representation, query_answer, evidence, usefulness, limitations]):
        return None, backend

    return (
        PaperSummary(
            core_idea=core_idea,
            representation_of_dynamics=representation,
            query_answer=query_answer,
            answer_strategy_key=strategy.key,
            answer_strategy_label=strategy.label,
            answer_evidence=answer_evidence,
            evidence=evidence,
            usefulness=usefulness,
            limitations=limitations,
            signature_terms=signature_terms,
            citation_sentences=citation_sentences,
        ),
        backend,
    )


def _build_question_answer_prompt(
    paper: ReviewPaper,
    question: str,
    source_text: str,
    *,
    used_full_text: bool,
) -> str:
    source_label = "full extracted paper text" if used_full_text else "abstract or sparse extracted text"
    return (
        "You are answering a research question about one paper.\n"
        "Your job is to read the provided paper text and answer ONLY from that text.\n"
        "Do not invent facts. Do not smooth over uncertainty. If the paper does not answer the question directly, say that explicitly.\n"
        "Prefer extractive phrasing grounded in the paper text. Preserve the paper's claims, setup, and limitations faithfully.\n"
        "Do not paraphrase concrete facts when a direct wording from the paper is available in the source text.\n"
        "Write the answer as detailed as possible while staying grounded in the source.\n\n"
        "Return valid JSON only with this exact schema:\n"
        "{\n"
        '  "short_answer": string,\n'
        '  "detailed_answer": string,\n'
        '  "evidence": [string, string, string],\n'
        '  "limitations": string\n'
        "}\n\n"
        "Field rules:\n"
        "- short_answer: 1-3 sentences answering the question directly.\n"
        "- detailed_answer: a detailed markdown-ready paragraph or paragraphs grounded in the paper text; include method details, representation details, and any caveats stated in the source.\n"
        "- evidence: 3-8 verbatim snippets copied from the source text that best support the answer.\n"
        "- limitations: one short note about source coverage; mention whether the answer used full text or only abstract-level text.\n\n"
        f"Question: {question}\n"
        f"Paper title: {paper.title}\n"
        f"ArXiv URL: {paper.arxiv_url}\n"
        f"Matched terms: {', '.join(paper.matched_terms) if paper.matched_terms else 'n/a'}\n"
        f"Source quality: {source_label}\n\n"
        "Paper abstract:\n"
        f"{paper.abstract or 'No abstract available.'}\n\n"
        "Paper text:\n"
        f"{source_text}\n"
    )

def _generate_question_answer_with_llm(
    paper: ReviewPaper,
    question: str,
    source_text: str,
    *,
    used_full_text: bool,
) -> tuple[str | None, str | None, tuple[str, ...], str | None, str | None]:
    load_env_file()
    prompt = _build_question_answer_prompt(
        paper,
        question,
        source_text,
        used_full_text=used_full_text,
    )
    text, backend = run_agent(prompt, cwd=get_workspace().agent_cwd())
    if not text:
        return None, None, (), None, backend
    payload = _extract_json_object(text)
    if not payload:
        return None, None, (), None, backend

    short_answer = _normalize_text(str(payload.get("short_answer") or ""))
    detailed_answer = str(payload.get("detailed_answer") or "").strip()
    evidence = _normalize_llm_evidence(payload.get("evidence"))
    limitations = _normalize_text(str(payload.get("limitations") or ""))
    if not short_answer or not detailed_answer:
        return None, None, (), None, backend
    if not limitations:
        limitations = (
            "Answer generated by the LLM agent from the extracted full text."
            if used_full_text
            else "Answer generated by the LLM agent from the abstract or sparse extracted text."
        )
    return short_answer, detailed_answer, evidence, limitations, backend


def _abstract_sentences(text: str, *, limit: int = 4) -> tuple[str, ...]:
    normalized = _normalize_text(text)
    if not normalized:
        return ()
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    picked = [part.strip() for part in parts if part.strip()]
    return tuple(picked[:limit])


def _generate_question_answer_from_abstract(
    paper: ReviewPaper,
    question: str,
    source_text: str,
    *,
    used_full_text: bool,
) -> tuple[str, str, tuple[str, ...], str, str]:
    body = _normalize_text(source_text or paper.abstract or paper.title)
    sentences = _abstract_sentences(body)
    short_answer = (
        " ".join(sentences[:2])
        if sentences
        else body[:280] + ("…" if len(body) > 280 else "")
    )
    comprehensive_answer = body[:4000] + ("…" if len(body) > 4000 else "")
    evidence = sentences[:4] if sentences else (body[:220] + ("…" if len(body) > 220 else ""),)
    limitations = (
        "Эвристический ответ по полному тексту без LLM-агента."
        if used_full_text
        else "Эвристический ответ по абстракту без LLM-агента."
    )
    return short_answer, comprehensive_answer, evidence, limitations, "abstract_heuristic"


def _paper_answer_token_set(artifact: PaperAnswerArtifact) -> set[str]:
    title_tokens = _meaningful_tokens(artifact.title)
    if len(title_tokens) >= 2:
        return title_tokens
    return _meaningful_tokens(
        " ".join([artifact.title, artifact.short_answer[:400], artifact.comprehensive_answer[:400]])
    )


def _token_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _build_cluster_from_members(
    question: str,
    members: list[PaperAnswerArtifact],
    *,
    index: int,
) -> PaperAnswerCluster:
    term_counts: Counter[str] = Counter()
    for member in members:
        term_counts.update(_paper_answer_token_set(member))
    signature_terms = tuple(term for term, _count in term_counts.most_common(6) if term)
    label_terms = signature_terms[:3] or ("papers",)
    label = " · ".join(term.replace("-", " ") for term in label_terms).title()
    shared_answer = (
        f"Papers in this group share themes around {', '.join(signature_terms[:4]) or 'related topics'} "
        f"for: {question}"
    )
    key = _slugify(label, fallback=f"answer-cluster-{index:02d}")
    return PaperAnswerCluster(
        key=key,
        label=label,
        answer=shared_answer,
        rationale=f"Grouped {len(members)} paper(s) by title and topic token overlap.",
        distinguishing_features="Heuristic cluster from abstract/title overlap without LLM.",
        signature_terms=signature_terms,
        paper_titles=tuple(member.title for member in members),
    )


def _split_cluster_if_diverse(members: list[PaperAnswerArtifact]) -> list[list[PaperAnswerArtifact]]:
    if len(members) < 4:
        return [members]

    token_sets = {member.title: _paper_answer_token_set(member) for member in members}
    avg_similarity: dict[str, float] = {}
    for member in members:
        others = [other for other in members if other.title != member.title]
        if not others:
            avg_similarity[member.title] = 1.0
            continue
        avg_similarity[member.title] = sum(
            _token_jaccard(token_sets[member.title], token_sets[other.title]) for other in others
        ) / len(others)

    outlier = min(members, key=lambda member: avg_similarity[member.title])
    if avg_similarity[outlier.title] >= 0.18:
        return [members]

    group_a = [outlier]
    group_b = [member for member in members if member.title != outlier.title]
    if len(group_b) < 1:
        return [members]
    return [group_a, group_b]


def _cluster_paper_answers_heuristic(
    question: str,
    artifacts: list[PaperAnswerArtifact],
) -> list[PaperAnswerCluster]:
    if not artifacts:
        return []

    remaining = list(artifacts)
    grouped: list[list[PaperAnswerArtifact]] = []
    token_sets = {artifact.title: _paper_answer_token_set(artifact) for artifact in artifacts}

    while remaining:
        seed = remaining.pop(0)
        seed_tokens = token_sets[seed.title]
        members = [seed]
        next_remaining: list[PaperAnswerArtifact] = []
        for artifact in remaining:
            other_tokens = token_sets[artifact.title]
            overlap = _token_jaccard(seed_tokens, other_tokens)
            if overlap >= 0.22:
                members.append(artifact)
            else:
                next_remaining.append(artifact)
        remaining = next_remaining
        grouped.extend(_split_cluster_if_diverse(members))

    clusters: list[PaperAnswerCluster] = []
    for index, members in enumerate(grouped, start=1):
        clusters.append(_build_cluster_from_members(question, members, index=index))
    return clusters


def _normalize_cluster_titles(
    value: object,
    *,
    valid_titles: tuple[str, ...],
) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    title_map = {_normalize_text(title).casefold(): title for title in valid_titles}
    matched: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        resolved = title_map.get(_normalize_text(item).casefold())
        if resolved:
            matched.append(resolved)
    return tuple(_unique_in_order(matched))


def _parse_paper_answer_clusters(
    payload: dict[str, object],
    *,
    valid_titles: tuple[str, ...],
) -> list[PaperAnswerCluster] | None:
    raw_clusters = payload.get("clusters")
    if not isinstance(raw_clusters, list) or not raw_clusters:
        return None

    clusters: list[PaperAnswerCluster] = []
    seen_keys: set[str] = set()
    assigned_titles: list[str] = []
    valid_title_set = set(valid_titles)

    for index, item in enumerate(raw_clusters, start=1):
        if not isinstance(item, dict):
            return None
        label = _normalize_text(str(item.get("label") or ""))
        answer = str(item.get("answer") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        distinguishing_features = str(item.get("distinguishing_features") or "").strip()
        paper_titles = _normalize_cluster_titles(
            item.get("paper_titles"),
            valid_titles=valid_titles,
        )
        signature_terms = _normalize_llm_terms(item.get("signature_terms"), limit=8)
        if not all([label, answer, rationale, distinguishing_features]) or not paper_titles:
            return None
        if not set(paper_titles).issubset(valid_title_set):
            return None
        key = _slugify(label, fallback=f"answer-cluster-{index}")
        if key in seen_keys:
            key = f"{key}-{index:02d}"
        seen_keys.add(key)
        assigned_titles.extend(paper_titles)
        clusters.append(
            PaperAnswerCluster(
                key=key,
                label=label,
                answer=answer,
                rationale=rationale,
                distinguishing_features=distinguishing_features,
                signature_terms=signature_terms,
                paper_titles=paper_titles,
            )
        )

    if set(assigned_titles) != valid_title_set:
        return None
    if len(assigned_titles) != len(valid_titles):
        return None
    return clusters


def _build_paper_answer_cluster_prompt(
    question: str,
    answer_documents: list[tuple[str, str]],
) -> str:
    docs_text = "\n\n".join(
        f"## Paper Answer File: {title}\n\n{content}" for title, content in answer_documents
    )
    return (
        "You are synthesizing a literature review from per-paper answer files.\n"
        "Your job is to propose clusters of papers based ONLY on the provided answer markdown files.\n"
        "Do not use background knowledge. Do not invent papers or merge papers by application area alone.\n"
        "Cluster papers by substantively different answers to the research question.\n"
        "Every paper must belong to exactly one cluster.\n"
        "The rationale for each cluster must explain why this cluster should exist as a distinct answer family.\n\n"
        "Return valid JSON only with this exact schema:\n"
        "{\n"
        '  "clusters": [\n'
        "    {\n"
        '      "label": string,\n'
        '      "answer": string,\n'
        '      "rationale": string,\n'
        '      "distinguishing_features": string,\n'
        '      "signature_terms": [string],\n'
        '      "paper_titles": [string]\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Field rules:\n"
        "- label: short cluster name.\n"
        "- answer: 1-3 sentences stating the common answer this cluster gives to the question.\n"
        "- rationale: 2-4 sentences arguing why these papers should be grouped together and why this cluster is distinct from the others.\n"
        "- distinguishing_features: 1-3 sentences naming the boundary of the cluster and how it differs from nearby clusters.\n"
        "- signature_terms: 3-8 short phrases that capture the cluster's answer.\n"
        "- paper_titles: exact paper titles from the provided files; every paper must appear exactly once across all clusters.\n\n"
        f"Research question: {question}\n\n"
        "Per-paper answer files:\n"
        f"{docs_text}\n"
    )


def _generate_paper_answer_clusters_with_llm(
    question: str,
    answer_documents: list[tuple[str, str]],
) -> tuple[list[PaperAnswerCluster] | None, str | None]:
    load_env_file()
    prompt = _build_paper_answer_cluster_prompt(question, answer_documents)
    text, backend = run_agent(prompt, cwd=get_workspace().agent_cwd())
    if not text:
        return None, backend
    payload = _extract_json_object(text)
    if not payload:
        return None, backend
    clusters = _parse_paper_answer_clusters(
        payload,
        valid_titles=tuple(title for title, _content in answer_documents),
    )
    return clusters, backend


def _assignment_rationale(
    paper: ReviewPaper,
    summary: PaperSummary,
    cluster: ProposedCluster,
) -> str:
    citations = list(summary.answer_evidence[:2]) or list(summary.citation_sentences[:2])
    lines = [
        f"This paper belongs in the cluster '{cluster.label}' because its answer strategy is '{summary.answer_strategy_label.lower()}'.",
        f"Its direct answer to the query is: {summary.query_answer}",
    ]
    if citations:
        lines.append(
            f"Key evidence: \"{_quote_excerpt(citations[0])}\"."
        )
    if len(citations) > 1:
        lines.append(
            f"Additional evidence: \"{_quote_excerpt(citations[1])}\"."
        )
    return " ".join(lines)


def propose_clusters(
    query: str,
    papers: list[ReviewPaper],
    summaries: dict[str, PaperSummary],
) -> list[ProposedCluster]:
    grouped: dict[str, list[tuple[ReviewPaper, PaperSummary]]] = {}
    for paper in papers:
        summary = summaries[paper.title]
        grouped.setdefault(summary.answer_strategy_key, []).append((paper, summary))

    clusters: list[ProposedCluster] = []
    grouped_sorted = sorted(
        grouped.items(),
        key=lambda item: (-len(item[1]), ANSWER_STRATEGY_BY_KEY[item[0]].label),
    )
    for index, (strategy_key, members) in enumerate(grouped_sorted, start=1):
        strategy = ANSWER_STRATEGY_BY_KEY.get(strategy_key, ANSWER_STRATEGY_BY_KEY["static_relational"])
        signature_terms = tuple(
            _unique_in_order(
                [term for _paper, summary in members for term in summary.signature_terms]
                + list(strategy.keywords[:3])
            )[:6]
        )
        rationale = (
            f"Grouped from {len(members)} paper(s) because the LLM assigned the same representation strategy: {strategy.answer_hint.lower()}"
        )
        clusters.append(
            ProposedCluster(
                key=f"cluster_{index:02d}_{_slugify(strategy.label, fallback='cluster')}",
                strategy_key=strategy.key,
                label=strategy.label,
                answer_hint=strategy.answer_hint,
                answer=strategy.answer if query else strategy.answer_hint,
                direction=strategy.direction,
                signature_terms=signature_terms,
                rationale=rationale,
            )
        )

    return clusters


def classify_papers_to_clusters(
    papers: list[ReviewPaper],
    summaries: dict[str, PaperSummary],
    clusters: list[ProposedCluster],
) -> dict[str, ProposedCluster]:
    cluster_by_strategy = {cluster.strategy_key: cluster for cluster in clusters}
    assignments: dict[str, ProposedCluster] = {}
    for paper in papers:
        summary = summaries[paper.title]
        cluster = cluster_by_strategy.get(summary.answer_strategy_key, clusters[0])
        assignments[paper.title] = cluster
    return assignments


def summarize_paper(paper: ReviewPaper, full_text: str) -> PaperSummary:
    source_text = full_text or paper.abstract or paper.title
    summary, _backend = _generate_paper_summary_with_llm(
        paper,
        source_text,
        used_full_text=bool(full_text),
    )
    if summary is None:
        raise RuntimeError(
            f"LLM summary generation failed for '{paper.title}'. No heuristic fallback is enabled."
        )
    return summary


def build_paper_summary_markdown(
    paper: ReviewPaper,
    summary: PaperSummary,
    *,
    rank: int,
    html_path: Path | None,
    pdf_path: Path | None,
    text_path: Path | None,
    extracted_text_chars: int,
    summary_backend: str | None,
    cluster: ProposedCluster,
    cluster_assignment_rationale: str,
) -> str:
    score_text = f"{paper.score:.3f}" if paper.score is not None else "n/a"
    matched_terms = ", ".join(paper.matched_terms) if paper.matched_terms else "n/a"
    full_text_status = "yes" if extracted_text_chars > 0 else "no"
    evidence_snippets = (
        " ".join(f'"{_quote_excerpt(snippet)}"' for snippet in summary.answer_evidence)
        if summary.answer_evidence
        else "No direct evidence snippet extracted."
    )
    return (
        f"# {paper.title}\n\n"
        f"- Rank: {rank}\n"
        f"- Query: {paper.query or 'n/a'}\n"
        f"- Score: {score_text}\n"
        f"- ArXiv: {paper.arxiv_url}\n"
        f"- ArXiv ID: {extract_arxiv_id(paper.arxiv_url)}\n"
        f"- Source report: {paper.source_report}\n"
        f"- Matched terms: {matched_terms}\n"
        f"- Full text extracted: {full_text_status}\n"
        f"- Extracted text chars: {extracted_text_chars}\n"
        f"- HTML cache: {html_path.name if html_path else 'not available'}\n"
        f"- PDF cache: {pdf_path.name if pdf_path else 'not available'}\n"
        f"- Text cache: {text_path.name if text_path else 'not available'}\n"
        f"- Summary backend: {summary_backend or 'n/a'}\n\n"
        "## Abstract\n\n"
        f"{paper.abstract or 'No abstract available.'}\n\n"
        "## Auto Summary\n\n"
        f"**Core idea.** {summary.core_idea}\n\n"
        f"**How dynamics are represented.** {summary.representation_of_dynamics}\n\n"
        f"**Direct answer to the query.** {summary.query_answer}\n\n"
        f"**Answer strategy.** {summary.answer_strategy_label}\n\n"
        f"**Evidence snippets.** {evidence_snippets}\n\n"
        f"**Evidence / setup.** {summary.evidence}\n\n"
        f"**Why it matters for the question.** {summary.usefulness}\n\n"
        f"**Limitations / caution.** {summary.limitations}\n\n"
        "## Cluster Assignment\n\n"
        f"- Proposed answer family: {cluster.answer_hint}\n"
        f"- Assigned cluster: {cluster.label}\n"
        f"- Cluster key: {cluster.key}\n"
        f"- Assignment rationale: {cluster_assignment_rationale}\n"
    )


def build_paper_question_markdown(
    paper: ReviewPaper,
    *,
    question: str,
    rank: int,
    html_path: Path | None,
    pdf_path: Path | None,
    text_path: Path | None,
    extracted_text_chars: int,
    answer_backend: str | None,
    answer_source: str,
    short_answer: str,
    comprehensive_answer: str,
    evidence: tuple[str, ...],
    limitations: str,
) -> str:
    score_text = f"{paper.score:.3f}" if paper.score is not None else "n/a"
    matched_terms = ", ".join(paper.matched_terms) if paper.matched_terms else "n/a"
    full_text_status = "yes" if extracted_text_chars > 0 else "no"
    evidence_block = (
        "\n".join(f"- \"{_quote_excerpt(snippet, limit=320)}\"" for snippet in evidence)
        if evidence
        else "- No direct evidence snippet extracted."
    )
    return (
        f"# {paper.title}\n\n"
        f"- Rank: {rank}\n"
        f"- Question: {question or 'n/a'}\n"
        f"- Score: {score_text}\n"
        f"- ArXiv: {paper.arxiv_url}\n"
        f"- ArXiv ID: {extract_arxiv_id(paper.arxiv_url)}\n"
        f"- Source report: {paper.source_report}\n"
        f"- Matched terms: {matched_terms}\n"
        f"- Full text extracted: {full_text_status}\n"
        f"- Extracted text chars: {extracted_text_chars}\n"
        f"- HTML cache: {html_path.name if html_path else 'not available'}\n"
        f"- PDF cache: {pdf_path.name if pdf_path else 'not available'}\n"
        f"- Text cache: {text_path.name if text_path else 'not available'}\n\n"
        "## Answer Generation\n\n"
        f"- Source: {answer_source}\n"
        f"- Backend: {answer_backend or 'n/a'}\n\n"
        "## Abstract\n\n"
        f"{paper.abstract or 'No abstract available.'}\n\n"
        "## Direct Answer\n\n"
        f"{short_answer}\n\n"
        "## Detailed Answer\n\n"
        f"{comprehensive_answer}\n\n"
        "## Evidence From The Paper\n\n"
        f"{evidence_block}\n\n"
        "## Limitations / Caution\n\n"
        f"{limitations}\n"
    )


def build_question_answer_index_markdown(
    question: str,
    artifacts: list[PaperAnswerArtifact],
    *,
    clusters: list[PaperAnswerCluster] | None = None,
    cluster_report_path: str | None = None,
) -> str:
    lines = [
        "# Paper Answers",
        "",
        f"- Question: {question or 'n/a'}",
        f"- Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Papers analyzed: {len(artifacts)}",
        f"- Cluster report: {cluster_report_path or 'n/a'}",
        "",
    ]
    if clusters:
        lines.extend(
            [
                "## Proposed Clusters",
                "",
            ]
        )
        for cluster in clusters:
            lines.extend(
                [
                    f"### {cluster.label}",
                    "",
                    f"**Cluster answer.** {cluster.answer}",
                    "",
                    f"**Why this cluster should exist.** {cluster.rationale}",
                    "",
                    f"**How it differs.** {cluster.distinguishing_features}",
                    "",
                    f"**Papers.** {', '.join(cluster.paper_titles)}",
                    "",
                ]
            )

    lines.extend(
        [
        "## Answers",
        "",
        ]
    )
    for artifact in artifacts:
        lines.extend(
            [
                f"### {artifact.title}",
                "",
                f"**Direct answer.** {artifact.short_answer}",
                "",
                f"**Backend.** {artifact.answer_backend or 'n/a'}",
                "",
                f"**Cluster.** {artifact.cluster_label or 'n/a'}",
                "",
            ]
        )
        if artifact.evidence:
            lines.append(f"**Top evidence.** \"{_quote_excerpt(artifact.evidence[0], limit=260)}\"")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_paper_answer_cluster_report(
    question: str,
    artifacts: list[PaperAnswerArtifact],
    clusters: list[PaperAnswerCluster],
    *,
    cluster_backend: str | None,
) -> str:
    artifact_by_title = {artifact.title: artifact for artifact in artifacts}
    lines = [
        "# Answer Clusters",
        "",
        f"- Question: {question or 'n/a'}",
        f"- Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Cluster backend: {cluster_backend or 'n/a'}",
        f"- Papers analyzed: {len(artifacts)}",
        "",
        "## Reading Of The Answer Files",
        "",
        "These clusters were proposed from the per-paper answer markdown files, not from title-level heuristics or keyword grouping.",
        "",
    ]
    for cluster in clusters:
        lines.extend(
            [
                f"## {cluster.label}",
                "",
                f"**Shared answer.** {cluster.answer}",
                "",
                f"**Why this cluster should exist.** {cluster.rationale}",
                "",
                f"**How it differs from nearby clusters.** {cluster.distinguishing_features}",
                "",
                f"**Signature terms.** {', '.join(cluster.signature_terms) if cluster.signature_terms else 'n/a'}",
                "",
                "**Papers in this cluster.**",
            ]
        )
        for title in cluster.paper_titles:
            artifact = artifact_by_title.get(title)
            if artifact is None:
                continue
            lines.append(f"- {artifact.title}: {artifact.short_answer}")
            lines.append(f"  - Why assigned here: {artifact.cluster_rationale or cluster.rationale}")
            for snippet in artifact.evidence[:2]:
                lines.append(f"  - Evidence: \"{_quote_excerpt(snippet)}\"")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _build_related_works_prompt(
    *,
    project_id: str,
    question: str,
    problem: str,
    clusters: list[PaperAnswerCluster],
    artifacts: list[PaperAnswerArtifact],
) -> str:
    artifact_by_title = {artifact.title: artifact for artifact in artifacts}
    cluster_blocks: list[str] = []
    for cluster in clusters:
        lines = [
            f"Cluster: {cluster.label}",
            f"Shared answer: {cluster.answer}",
            f"Why this cluster exists: {cluster.rationale}",
            f"How it differs: {cluster.distinguishing_features}",
            f"Signature terms: {', '.join(cluster.signature_terms) if cluster.signature_terms else 'n/a'}",
            "Papers:",
        ]
        for title in cluster.paper_titles:
            artifact = artifact_by_title.get(title)
            if artifact is None:
                continue
            year = f" ({artifact.year})" if artifact.year is not None else ""
            lines.append(f"- {artifact.title}{year}")
            lines.append(f"  Short answer: {artifact.short_answer}")
            lines.append(f"  Detailed answer: {artifact.comprehensive_answer}")
            if artifact.evidence:
                lines.append(
                    f"  Evidence: {' | '.join(_quote_excerpt(snippet, limit=220) for snippet in artifact.evidence[:2])}"
                )
            lines.append(f"  Limitations: {artifact.limitations}")
        cluster_blocks.append("\n".join(lines))

    return (
        "You are writing the Related Works section for a research paper.\n\n"
        "Return markdown only, with no code fences.\n"
        "Write a concise but substantive section that synthesizes the selected literature clusters into a coherent narrative.\n"
        "Do not merely list papers one by one. Merge nearby clusters when helpful and explicitly compare their assumptions, representations, and limitations.\n"
        "Ground every claim only in the provided cluster and paper summaries.\n"
        "Prefer citation-style mentions by paper title in prose.\n"
        "Structure requirements:\n"
        "- Start with the heading `## Related Works`.\n"
        "- Write 2-5 paragraphs.\n"
        "- The first paragraph should frame the literature relative to the target problem.\n"
        "- Middle paragraphs should synthesize the selected clusters, including similarities and differences.\n"
        "- End with a brief gap statement explaining what remains unresolved for this problem.\n"
        "- Avoid bullet lists unless absolutely necessary.\n\n"
        f"Project id: {project_id}\n"
        f"Original paper-question prompt: {question or 'n/a'}\n"
        f"Target problem for the paper: {problem.strip()}\n\n"
        "Selected cluster material:\n\n"
        + "\n\n".join(cluster_blocks)
    )


def prepare_related_work_material(
    project_id: str,
    problem: str,
    cluster_keys: list[str],
) -> dict[str, object]:
    from koi.services.review.artifacts import _paper_answer_artifact_from_dict

    normalized_problem = str(problem or "").strip()
    if not normalized_problem:
        raise ValueError("Problem statement must not be empty.")

    payload = load_latest_paper_answer_run(project_id)
    if payload is None:
        raise ValueError("No saved paper answer run was found for this project.")

    raw_papers = payload.get("papers")
    if not isinstance(raw_papers, list) or not raw_papers:
        raise ValueError("Latest paper answer run does not contain paper summaries.")

    artifacts: list[PaperAnswerArtifact] = []
    for item in raw_papers:
        if not isinstance(item, dict):
            continue
        artifact = _paper_answer_artifact_from_dict(item)
        if artifact is not None:
            artifacts.append(artifact)
    if not artifacts:
        raise ValueError("Latest paper answer run does not contain valid paper artifacts.")

    valid_titles = tuple(artifact.title for artifact in artifacts)
    clusters = _parse_paper_answer_clusters(
        {"clusters": payload.get("clusters")},
        valid_titles=valid_titles,
    )
    if not clusters:
        raise ValueError("Latest paper answer run does not contain valid answer clusters.")

    wanted = {str(key).strip() for key in cluster_keys if str(key).strip()}
    if not wanted:
        raise ValueError("Select at least one cluster before generating Related Works.")

    selected_clusters = [cluster for cluster in clusters if cluster.key in wanted]
    if not selected_clusters:
        raise ValueError("Selected clusters were not found in the latest paper answer run.")

    selected_titles = {title for cluster in selected_clusters for title in cluster.paper_titles}
    selected_artifacts = [artifact for artifact in artifacts if artifact.title in selected_titles]
    prompt = _build_related_works_prompt(
        project_id=project_id,
        question=str(payload.get("question") or ""),
        problem=normalized_problem,
        clusters=selected_clusters,
        artifacts=selected_artifacts,
    )
    return {
        "project_id": project_id,
        "question": str(payload.get("question") or ""),
        "problem": normalized_problem,
        "cluster_keys": [cluster.key for cluster in selected_clusters],
        "cluster_labels": [cluster.label for cluster in selected_clusters],
        "paper_count": len(selected_artifacts),
        "prompt": prompt,
    }


def generate_related_works_section(
    project_id: str,
    problem: str,
    cluster_keys: list[str],
) -> dict[str, object]:
    material = prepare_related_work_material(project_id, problem, cluster_keys)
    text, backend = run_agent(str(material["prompt"]), cwd=get_workspace().agent_cwd())
    markdown = _strip_code_fences(text or "").strip()
    if not markdown:
        raise RuntimeError("No agent backend is available for Related Works generation.")

    return {
        "project_id": project_id,
        "question": material["question"],
        "problem": material["problem"],
        "cluster_keys": material["cluster_keys"],
        "cluster_labels": material["cluster_labels"],
        "paper_count": material["paper_count"],
        "backend": backend,
        "markdown": markdown,
        "status": "answered",
    }


def _paper_reviews_root(project_id: str) -> Path:
    return paper_reviews_dir(project_id)


def _paper_answers_root(project_id: str) -> Path:
    return paper_answers_dir(project_id)


def _repo_agent_bundles_root(project_id: str) -> Path:
    return agent_bundles_dir(project_id)


def _top_level_index_path(project_id: str) -> Path:
    return _paper_reviews_root(project_id) / "index.json"


def _load_top_level_index(project_id: str) -> list[dict[str, object]]:
    path = _top_level_index_path(project_id)
    if not path.exists():
        return []
    try:
        data = _read_json(path)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save_top_level_index(project_id: str, rows: list[dict[str, object]]) -> None:
    path = _top_level_index_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _paper_answers_index_path(project_id: str) -> Path:
    return _paper_answers_root(project_id) / "index.json"


def _load_paper_answers_index(project_id: str) -> list[dict[str, object]]:
    path = _paper_answers_index_path(project_id)
    if not path.exists():
        return []
    try:
        data = _read_json(path)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save_paper_answers_index(project_id: str, rows: list[dict[str, object]]) -> None:
    path = _paper_answers_index_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_latest_paper_answer_run(project_id: str) -> dict[str, object] | None:
    rows = _load_paper_answers_index(project_id)
    if not rows:
        return None
    latest = max(
        rows,
        key=lambda row: str(row.get("created_at") or ""),
    )
    folder = _normalize_text(str(latest.get("folder") or ""))
    if not folder:
        return None
    manifest_path = _paper_answers_root(project_id) / folder / "index.json"
    if not manifest_path.exists():
        return None
    try:
        payload = _read_json(manifest_path)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    result = dict(payload)
    result.setdefault("project_id", project_id)
    result.setdefault("folder", folder)
    result.setdefault("path", f"paper_answers/{folder}")
    index_markdown = _normalize_text(str(result.get("index_markdown") or ""))
    if index_markdown and not index_markdown.startswith("paper_answers/"):
        result["index_markdown"] = f"paper_answers/{folder}/{index_markdown}"
    cluster_report = _normalize_text(str(result.get("cluster_report") or ""))
    if cluster_report and not cluster_report.startswith("paper_answers/"):
        result["cluster_report"] = f"paper_answers/{folder}/{cluster_report}"
    return result


def build_cluster_report(
    query: str,
    clusters: list[ProposedCluster],
    artifacts: list[PaperArtifact],
    summaries: dict[str, PaperSummary],
) -> str:
    grouped: dict[str, list[PaperArtifact]] = {cluster.key: [] for cluster in clusters}
    for artifact in artifacts:
        grouped.setdefault(artifact.cluster_key, []).append(artifact)

    lines = [
        "# Cluster Directions",
        "",
        f"- Query: {query or 'n/a'}",
        f"- Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- Papers analyzed: {len(artifacts)}",
        "",
        "## Reading Of The Literature",
        "",
        "These clusters describe different ways the literature answers the question, not just different application areas.",
        "",
    ]

    lines.extend(
        [
            "## Proposed Clusters",
            "",
            "The agent proposed these clusters after reading the paper summaries and looking for repeated answer patterns.",
            "",
        ]
    )

    for cluster in clusters:
        lines.append(f"- {cluster.label}: {cluster.rationale}")
    lines.append("")

    for cluster in clusters:
        members = grouped.get(cluster.key, [])
        if not members:
            continue
        lines.extend(
            [
                f"## {cluster.label}",
                "",
                f"**Answer to the question.** {cluster.answer}",
                "",
                f"**Cluster answer hint.** {cluster.answer_hint}",
                "",
                f"**Suggested research direction.** {cluster.direction}",
                "",
                f"**Signature terms.** {', '.join(cluster.signature_terms) if cluster.signature_terms else 'n/a'}",
                "",
                "**Papers in this answer family.**",
            ]
        )
        for artifact in members:
            summary = summaries[artifact.title]
            lines.append(
                f"- {artifact.title}: {summary.query_answer}"
            )
            for snippet in summary.answer_evidence[:2]:
                lines.append(f"  - Evidence: \"{_quote_excerpt(snippet)}\"")
        lines.append("")

    return "\n".join(lines).strip() + "\n"

