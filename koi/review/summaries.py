from __future__ import annotations

import re

from koi.adapters.agent_backends import run_agent
from koi.adapters.settings_store import load_env_file
from koi.adapters.workspace import get_workspace
from koi.review.models import ANSWER_STRATEGY_BY_KEY, PaperSummary, ReviewPaper
from koi.review.parsing import (
    _extract_json_object, _normalize_llm_evidence, _normalize_llm_terms,
    _normalize_strategy_key, _strategy_catalog_text,
)
from koi.review.util import _normalize_text

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
        "Heuristic full-text answer without an LLM agent."
        if used_full_text
        else "Heuristic abstract-based answer without an LLM agent."
    )
    return short_answer, comprehensive_answer, evidence, limitations, "abstract_heuristic"



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
