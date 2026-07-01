from __future__ import annotations

import csv
import json
import math
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from koi.adapters.agent_backends import run_agent
from koi.adapters.paths import paper_reviews_dir
from koi.adapters.workspace import get_workspace

_ws = get_workspace()
LIBRARY_UPLOAD_PATH = _ws.library_upload
LIBRARY_CSV_CANDIDATES = _ws.library_csv_candidates()
PAPER_REVIEWS_DIRNAME = "paper_reviews"
LIBRARY_REQUIRED_FIELDS = ("no", "arxiv_url", "title", "authors", "abstract")
LIBRARY_FIELDNAMES = ("no", "arxiv_url", "title", "authors", "abstract")

TOKEN_RE = re.compile(r"[a-z0-9\u0400-\u04ff]+")
ARXIV_TOKEN_RE = re.compile(r"[a-z0-9\u0400-\u04ff]+(?:-[a-z0-9]+)?")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
ARXIV_MAX_QUERY_TERMS = 3

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "using",
    "via",
    "what",
    "which",
    "with",
}

ARXIV_QUERY_STOPWORDS = STOPWORDS | {
    "about",
    "across",
    "affect",
    "affects",
    "also",
    "among",
    "between",
    "both",
    "can",
    "could",
    "desktop",
    "does",
    "effect",
    "effects",
    "give",
    "have",
    "impact",
    "impacts",
    "into",
    "its",
    "may",
    "might",
    "more",
    "most",
    "much",
    "need",
    "only",
    "other",
    "over",
    "phone",
    "really",
    "same",
    "should",
    "show",
    "some",
    "such",
    "than",
    "them",
    "then",
    "there",
    "these",
    "they",
    "those",
    "through",
    "under",
    "very",
    "was",
    "were",
    "when",
    "where",
    "while",
    "will",
    "within",
    "without",
    "would",
    "your",
}

# Слишком общие для arXiv — без пары с доменными терминами тянут нерелевантные статьи.
ARXIV_QUERY_WEAK_TERMS = {
    "approach",
    "based",
    "data",
    "large",
    "learning",
    "method",
    "mobile",
    "model",
    "models",
    "network",
    "networks",
    "new",
    "paper",
    "results",
    "search",
    "show",
    "system",
    "systems",
    "using",
}


@dataclass(frozen=True)
class LibraryPaper:
    title: str
    arxiv_url: str
    abstract: str
    title_tokens: tuple[str, ...]
    title_token_set: frozenset[str]
    abstract_tokens: tuple[str, ...]
    abstract_token_set: frozenset[str]
    normalized_title: str
    normalized_abstract: str


@dataclass(frozen=True)
class AgentDiscoveredPaper:
    title: str
    arxiv_url: str
    authors: str
    abstract: str


def _tokenize(text: str) -> list[str]:
    tokens = [m.group(0) for m in TOKEN_RE.finditer((text or "").lower())]
    filtered = [token for token in tokens if token not in STOPWORDS]
    return filtered or tokens


def _normalize_spaces(text: str) -> str:
    return " ".join((text or "").strip().split())


def _slugify(text: str, fallback: str = "review") -> str:
    s = _normalize_spaces(text).lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:64] or fallback


def _safe_filename(text: str, fallback: str = "paper") -> str:
    s = _normalize_spaces(text)
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", "_", s).strip(" ._")
    return (s[:120] or fallback) + ".md"


def resolve_library_csv() -> Path:
    for path in LIBRARY_CSV_CANDIDATES:
        if path.exists():
            return path
    searched = ", ".join(str(path) for path in LIBRARY_CSV_CANDIDATES)
    raise FileNotFoundError(f"Library CSV not found. Checked: {searched}")


def reset_library_cache() -> None:
    load_library.cache_clear()
    token_idf.cache_clear()


def library_csv_exists() -> bool:
    return any(path.exists() for path in LIBRARY_CSV_CANDIDATES)


def _snippet(text: str, query_tokens: set[str], max_chars: int = 280) -> str:
    text = _normalize_spaces(text)
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    lowered = text.lower()
    best = -1
    for token in query_tokens:
        idx = lowered.find(token)
        if idx >= 0 and (best < 0 or idx < best):
            best = idx

    if best < 0:
        return text[: max_chars - 1].rstrip() + "…"

    start = max(0, best - 72)
    end = min(len(text), start + max_chars)
    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(text):
        excerpt = excerpt.rstrip() + "…"
    return excerpt


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


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


def _normalize_arxiv_url(url: str) -> str:
    text = _normalize_spaces(url).replace("http://", "https://").rstrip("/")
    if not text:
        return ""
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([a-z\-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", text, re.IGNORECASE)
    if not match:
        return ""
    return f"https://arxiv.org/abs/{match.group(1)}"


def _coerce_agent_papers(value: object) -> list[AgentDiscoveredPaper]:
    if not isinstance(value, list):
        return []

    papers: list[AgentDiscoveredPaper] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        title = _normalize_spaces(str(item.get("title") or ""))
        arxiv_url = _normalize_arxiv_url(str(item.get("arxiv_url") or ""))
        authors_value = item.get("authors")
        if isinstance(authors_value, list):
            authors = ", ".join(
                _normalize_spaces(str(author))
                for author in authors_value
                if _normalize_spaces(str(author))
            )
        else:
            authors = _normalize_spaces(str(authors_value or ""))
        abstract = _normalize_spaces(str(item.get("abstract") or ""))
        if not title or not arxiv_url or not authors or not abstract:
            continue
        key = (title.lower(), arxiv_url.lower())
        if key in seen:
            continue
        seen.add(key)
        papers.append(
            AgentDiscoveredPaper(
                title=title,
                arxiv_url=arxiv_url,
                authors=authors,
                abstract=abstract,
            )
        )
    return papers


def _library_bootstrap_prompt(query: str, limit: int) -> str:
    return f"""
You are bootstrapping a local literature CSV for a research workspace.

Task:
- Find up to {limit} highly relevant papers for the query below.
- Prefer using Google Scholar for discovery and keep only papers that have a verifiable arXiv abstract page.
- Prefer recent or canonical papers when both are relevant.
- Return only papers you can identify confidently enough to provide a real title, real arXiv URL, author list, and faithful abstract.

Hard constraints:
- Return exactly one JSON object and no prose outside JSON.
- JSON shape:
  {{
    "query": "string",
    "papers": [
      {{
        "title": "string",
        "arxiv_url": "https://arxiv.org/abs/....",
        "authors": "Author One, Author Two",
        "abstract": "string"
      }}
    ],
    "notes": "optional string"
  }}
- `papers` must be ranked best-first by relevance to the query.
- Deduplicate near-identical papers.
- `arxiv_url` must be an arXiv ABS URL, not a PDF URL.
- If you do not have live search access or are not confident in a paper's metadata, omit it instead of guessing.
- If you cannot confidently find {limit} valid arXiv-backed papers, return fewer rather than inventing data.
- Do not use markdown fences.

Research query:
{query.strip()}
""".strip()


def _write_library_csv(papers: list[AgentDiscoveredPaper], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LIBRARY_FIELDNAMES)
        writer.writeheader()
        for idx, paper in enumerate(papers, start=1):
            writer.writerow(
                {
                    "no": idx,
                    "arxiv_url": paper.arxiv_url,
                    "title": paper.title,
                    "authors": paper.authors,
                    "abstract": paper.abstract,
                }
            )


def _display_path(path: Path) -> str:
    try:
        return _ws.relative_to_workspace(path)
    except ValueError:
        return str(path)


def discover_library_with_agent(
    query: str,
    limit: int = 10,
    *,
    destination: Path = LIBRARY_UPLOAD_PATH,
) -> dict[str, object]:
    text = _normalize_spaces(query)
    if not text:
        raise ValueError("Query must not be empty")
    if limit < 1:
        raise ValueError("Limit must be positive")

    prompt = _library_bootstrap_prompt(text, min(limit, 50))
    response, backend = run_agent(prompt, cwd=_ws.agent_cwd(), timeout=180)
    if not response:
        raise RuntimeError(
            "No agent backend is available for library bootstrap. Configure a working agent backend first."
        )

    parsed = _extract_json_object(response)
    if parsed is None:
        raise RuntimeError("Agent returned invalid JSON while bootstrapping the library.")

    papers = _coerce_agent_papers(parsed.get("papers"))
    if not papers:
        raise RuntimeError(
            "Agent did not return any valid arXiv-backed papers for this query."
        )

    _write_library_csv(papers, destination)
    reset_library_cache()

    notes = _normalize_spaces(str(parsed.get("notes") or ""))
    return {
        "ok": True,
        "query": text,
        "count": len(papers),
        "csv_path": _display_path(destination),
        "fields": list(LIBRARY_FIELDNAMES),
        "required_fields": list(LIBRARY_REQUIRED_FIELDS),
        "backend": backend,
        "notes": notes,
        "papers": [
            {
                "title": paper.title,
                "arxiv_url": paper.arxiv_url,
                "authors": paper.authors,
                "abstract": paper.abstract,
            }
            for paper in papers
        ],
    }


@lru_cache(maxsize=1)
def load_library() -> tuple[LibraryPaper, ...]:
    papers: list[LibraryPaper] = []
    library_csv = resolve_library_csv()
    with library_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = _normalize_spaces(row.get("title", ""))
            arxiv_url = _normalize_spaces(row.get("arxiv_url", ""))
            if not title or not arxiv_url:
                continue
            abstract = _normalize_spaces(row.get("abstract", ""))
            title_tokens = tuple(_tokenize(title))
            abstract_tokens = tuple(_tokenize(abstract))
            papers.append(
                LibraryPaper(
                    title=title,
                    arxiv_url=arxiv_url,
                    abstract=abstract,
                    title_tokens=title_tokens,
                    title_token_set=frozenset(title_tokens),
                    abstract_tokens=abstract_tokens,
                    abstract_token_set=frozenset(abstract_tokens),
                    normalized_title=title.lower(),
                    normalized_abstract=abstract.lower(),
                )
            )
    return tuple(papers)


@lru_cache(maxsize=1)
def token_idf() -> dict[str, float]:
    papers = load_library()
    df: Counter[str] = Counter()
    for paper in papers:
        df.update(paper.title_token_set | paper.abstract_token_set)
    total = max(len(papers), 1)
    return {
        token: math.log((1 + total) / (1 + freq)) + 1.0 for token, freq in df.items()
    }


def search_library(query: str, limit: int = 10) -> list[dict[str, object]]:
    text = _normalize_spaces(query)
    if not text:
        return []

    query_tokens = _tokenize(text)
    if not query_tokens:
        return []

    idf = token_idf()
    query_token_set = set(query_tokens)
    query_norm = " ".join(query_tokens)
    query_bigrams = {
        (query_tokens[i], query_tokens[i + 1]) for i in range(len(query_tokens) - 1)
    }

    ranked: list[tuple[float, LibraryPaper, list[str]]] = []
    for paper in load_library():
        title_overlap = sorted(query_token_set & paper.title_token_set)
        abstract_overlap = sorted(query_token_set & paper.abstract_token_set)
        overlap = sorted(set(title_overlap) | set(abstract_overlap))
        title_seq = SequenceMatcher(None, text.lower(), paper.normalized_title).ratio()
        abstract_seq = (
            SequenceMatcher(None, text.lower(), paper.normalized_abstract).ratio()
            if paper.abstract
            else 0.0
        )

        if not overlap and max(title_seq, abstract_seq) < 0.22:
            continue

        title_overlap_score = sum(idf.get(token, 1.0) for token in title_overlap)
        abstract_overlap_score = sum(idf.get(token, 1.0) for token in abstract_overlap)
        abstract_phrase_hits = sum(
            1 for token in query_token_set if token in paper.normalized_abstract
        )

        title_bigrams = {
            (paper.title_tokens[i], paper.title_tokens[i + 1])
            for i in range(len(paper.title_tokens) - 1)
        }
        abstract_bigrams = {
            (paper.abstract_tokens[i], paper.abstract_tokens[i + 1])
            for i in range(len(paper.abstract_tokens) - 1)
        }
        bigram_overlap = len(query_bigrams & title_bigrams)
        abstract_bigram_overlap = len(query_bigrams & abstract_bigrams)
        contains_phrase = query_norm in paper.normalized_title
        abstract_contains_phrase = query_norm in paper.normalized_abstract

        score = 0.0
        score += title_overlap_score * 1.8
        score += abstract_overlap_score * 0.9
        score += 1.35 * bigram_overlap
        score += 0.8 * abstract_bigram_overlap
        score += 2.0 if contains_phrase else 0.0
        score += 1.25 if abstract_contains_phrase else 0.0
        score += min(abstract_phrase_hits, 6) * 0.22
        score += title_seq * 2.4
        score += abstract_seq * 1.1
        score /= 1.0 + max(len(paper.title_tokens) - 6, 0) * 0.04
        if paper.abstract_tokens:
            score /= 1.0 + max(len(paper.abstract_tokens) - 120, 0) * 0.0015

        if score <= 0.6:
            continue
        ranked.append((score, paper, overlap))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "title": paper.title,
            "arxiv_url": paper.arxiv_url,
            "score": round(score, 3),
            "matched_terms": overlap,
            "abstract": paper.abstract,
            "abstract_preview": _snippet(paper.abstract, query_token_set),
        }
        for score, paper, overlap in ranked[: max(1, min(limit, 50))]
    ]


def _needs_translation(text: str) -> bool:
    return bool(CYRILLIC_RE.search(text))


def _arxiv_query_tokens(text: str, *, max_terms: int = ARXIV_MAX_QUERY_TERMS) -> list[str]:
    raw = [m.group(0) for m in ARXIV_TOKEN_RE.finditer((text or "").lower())]
    seen: set[str] = set()
    candidates: list[str] = []
    for token in raw:
        if token in ARXIV_QUERY_STOPWORDS or len(token) < 2:
            continue
        if token in seen:
            continue
        seen.add(token)
        candidates.append(token)

    if not candidates:
        candidates = [token for token in raw if len(token) >= 2]
        if not candidates:
            return []

    def rank(token: str) -> tuple[int, int, int, int]:
        is_weak = token in ARXIV_QUERY_WEAK_TERMS
        is_acronym = len(token) <= 5 and (token.isupper() or token in {"ctr", "llm", "ppo", "nlp", "rl"})
        has_hyphen = "-" in token
        is_specific = len(token) >= 6 or token in {"ctr", "ads", "ad"}
        return (0 if is_weak else 1, is_acronym or has_hyphen, is_specific, len(token))

    candidates.sort(key=rank, reverse=True)
    strong = [token for token in candidates if token not in ARXIV_QUERY_WEAK_TERMS]
    weak = [token for token in candidates if token in ARXIV_QUERY_WEAK_TERMS]
    ordered = strong + weak
    return ordered[: max(1, max_terms)]


def _build_arxiv_search_query(text: str, *, max_terms: int = ARXIV_MAX_QUERY_TERMS) -> str:
    tokens = _arxiv_query_tokens(text, max_terms=max_terms)
    if not tokens:
        return ""
    if len(tokens) == 1:
        return f"all:{tokens[0]}"
    return "+AND+".join(f"all:{token}" for token in tokens)


def _fetch_arxiv_atom(search_q: str, limit: int) -> bytes | None:
    from urllib.parse import quote

    if not search_q:
        return None
    max_results = max(1, min(limit, 50))
    url = (
        f"{ARXIV_API_URL}?search_query={quote(search_q, safe='+:')}"
        f"&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "ResearchOS/1.0 (arxiv-api)"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError):
        return None


def _parse_arxiv_atom_feed(xml_bytes: bytes, query: str, limit: int) -> list[dict[str, object]]:
    root = ET.fromstring(xml_bytes)
    query_token_set = set(_arxiv_query_tokens(query, max_terms=12))
    if not query_token_set:
        query_token_set = set(_tokenize(query))
    results: list[tuple[float, dict[str, object]]] = []
    max_results = max(1, min(limit, 50))

    for idx, entry in enumerate(root.findall("atom:entry", ARXIV_ATOM_NS)):
        title = _normalize_spaces(entry.findtext("atom:title", default="", namespaces=ARXIV_ATOM_NS))
        summary = _normalize_spaces(entry.findtext("atom:summary", default="", namespaces=ARXIV_ATOM_NS))
        entry_id = entry.findtext("atom:id", default="", namespaces=ARXIV_ATOM_NS).strip()
        arxiv_url = _normalize_arxiv_url(entry_id) or entry_id

        authors: list[str] = []
        for author in entry.findall("atom:author", ARXIV_ATOM_NS):
            name = _normalize_spaces(author.findtext("atom:name", default="", namespaces=ARXIV_ATOM_NS))
            if name:
                authors.append(name)

        if not title or not arxiv_url:
            continue

        title_tokens = set(_tokenize(title))
        abstract_tokens = set(_tokenize(summary))
        overlap = sorted(query_token_set & (title_tokens | abstract_tokens))
        title_overlap = len(query_token_set & title_tokens)
        relevance = title_overlap * 2.0 + len(overlap) - idx * 0.05
        results.append(
            (
                relevance,
                {
                    "title": title,
                    "arxiv_url": arxiv_url,
                    "authors": ", ".join(authors),
                    "abstract": summary,
                    "abstract_preview": _snippet(summary, query_token_set)
                    if query_token_set
                    else short_preview(summary),
                    "score": round(max(0.65, 1.0 - idx * 0.03), 3),
                    "matched_terms": overlap,
                },
            )
        )

    results.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in results[:max_results]]


def short_preview(text: str, max_chars: int = 280) -> str:
    normalized = _normalize_spaces(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def search_arxiv_internet(query: str, limit: int = 10) -> list[dict[str, object]]:
    text = _normalize_spaces(query)
    if not text:
        return []

    all_tokens = _arxiv_query_tokens(text, max_terms=12)
    if not all_tokens:
        return []

    term_budgets = []
    for count in (ARXIV_MAX_QUERY_TERMS, 2, 1):
        if count not in term_budgets:
            term_budgets.append(count)

    for count in term_budgets:
        if len(all_tokens) < count:
            continue
        tokens = all_tokens[:count]
        if len(tokens) == 1:
            search_q = f"all:{tokens[0]}"
        else:
            search_q = "+AND+".join(f"all:{token}" for token in tokens)
        xml_bytes = _fetch_arxiv_atom(search_q, limit)
        if not xml_bytes:
            continue
        results = _parse_arxiv_atom_feed(xml_bytes, text, limit)
        if results:
            return results

    return []


def _translate_via_openrouter(text: str) -> tuple[str | None, str | None]:
    from koi.adapters.agent_backends import run_openrouter

    prompt = (
        "Translate the following literature-search question into natural, concise academic English.\n"
        "Preserve technical meaning and line breaks.\n"
        "Return only the translated English text.\n\n"
        f"{text}"
    )
    translated = run_openrouter(prompt, timeout=90)
    if translated:
        return translated.strip().strip('"'), "openrouter"
    return None, None


def _translate_via_mymemory(text: str) -> tuple[str | None, str | None]:
    from urllib.parse import quote

    chunk = text[:480]
    url = f"https://api.mymemory.translated.net/get?q={quote(chunk)}&langpair=ru|en"
    request = urllib.request.Request(url, headers={"User-Agent": "ResearchOS/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None, None

    translated = _normalize_spaces(
        str(((payload.get("responseData") or {}).get("translatedText")) or "")
    )
    if not translated or translated.upper() == chunk.upper():
        return None, None
    return translated, "mymemory"


def translate_to_english(text: str) -> tuple[str, str]:
    normalized = _normalize_spaces(text)
    if not normalized:
        return "", "none"
    if not _needs_translation(normalized):
        return normalized, "passthrough"

    prompt = (
        "Translate the following literature-search question into natural, concise academic English.\n"
        "Preserve technical meaning, paper titles, identifiers, bullet structure, and line breaks.\n"
        "Do not add explanations, notes, quotes, markdown fences, or any extra commentary.\n"
        "Return only the translated English text.\n\n"
        f"{normalized}"
    )
    translated, backend = run_agent(prompt, cwd=_ws.agent_cwd(), timeout=120)
    if translated:
        return translated.strip().strip('"'), backend or "agent"

    translated, backend = _translate_via_openrouter(normalized)
    if translated:
        return translated, backend

    translated, backend = _translate_via_mymemory(normalized)
    if translated:
        return translated, backend

    return normalized, "original"


def bootstrap_library_from_arxiv(
    query: str,
    limit: int = 10,
    *,
    destination: Path = LIBRARY_UPLOAD_PATH,
) -> dict[str, object]:
    text = _normalize_spaces(query)
    if not text:
        raise ValueError("Query must not be empty")
    if limit < 1:
        raise ValueError("Limit must be positive")

    results = search_arxiv_internet(text, min(limit, 50))
    if not results:
        raise RuntimeError("No papers found on arXiv for this query.")

    papers = [
        AgentDiscoveredPaper(
            title=str(result["title"]),
            arxiv_url=str(result["arxiv_url"]),
            authors=str(result.get("authors") or ""),
            abstract=str(result.get("abstract") or ""),
        )
        for result in results
    ]
    _write_library_csv(papers, destination)
    reset_library_cache()

    return {
        "ok": True,
        "query": text,
        "count": len(papers),
        "csv_path": _display_path(destination),
        "fields": list(LIBRARY_FIELDNAMES),
        "required_fields": list(LIBRARY_REQUIRED_FIELDS),
        "backend": "arxiv_api",
        "notes": "Imported from arXiv API search.",
        "papers": [
            {
                "title": paper.title,
                "arxiv_url": paper.arxiv_url,
                "authors": paper.authors,
                "abstract": paper.abstract,
            }
            for paper in papers
        ],
    }


def review_project_title(query: str, max_len: int = 72) -> str:
    title = f"Review Set: {query.strip()}"
    return title if len(title) <= max_len else title[: max_len - 1].rstrip() + "…"


def review_project_description(query: str, result_count: int) -> str:
    return (
        f"Research question: {query.strip()}\n\n"
        f"This project was generated automatically from the local literature library. "
        f"It contains {result_count} ranked paper candidates for screening and annotation."
    )


def build_review_report(result: dict[str, object], query: str) -> str:
    matched = result.get("matched_terms") or []
    matched_text = ", ".join(str(x) for x in matched) if matched else "n/a"
    abstract = str(result.get("abstract") or "").strip()
    return (
        f"# {result['title']}\n\n"
        f"- Query: {query.strip()}\n"
        f"- Score: {result['score']}\n"
        f"- ArXiv: {result['arxiv_url']}\n"
        f"- Matched terms: {matched_text}\n\n"
        "## Abstract\n\n"
        f"{abstract or 'No abstract available.'}\n\n"
        "## Screening Notes\n\n"
        "- Relevance:\n"
        "- Key contribution:\n"
        "- Useful methods / datasets:\n"
        "- Decision:\n"
    )


def review_card_id() -> str:
    return f"c-{uuid4().hex[:8]}"


def _paper_reviews_root(project_id: str) -> Path:
    return paper_reviews_dir(project_id)


def _paper_reviews_index_path(project_id: str) -> Path:
    return _paper_reviews_root(project_id) / "index.json"


def _load_paper_reviews_index(project_id: str) -> list[dict[str, object]]:
    path = _paper_reviews_index_path(project_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_paper_reviews_index(project_id: str, entries: list[dict[str, object]]) -> None:
    path = _paper_reviews_index_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unique_review_dir(project_id: str, query: str) -> Path:
    root = _paper_reviews_root(project_id)
    root.mkdir(parents=True, exist_ok=True)
    base = _slugify(query, fallback="paper-review")
    candidate = root / base
    n = 1
    while candidate.exists():
        n += 1
        candidate = root / f"{base}-{n}"
    return candidate


def create_project_paper_review(
    project_id: str, query: str, results: list[dict[str, object]]
) -> dict[str, object]:
    review_dir = _unique_review_dir(project_id, query)
    review_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    papers_meta: list[dict[str, object]] = []
    for idx, result in enumerate(results, start=1):
        filename = f"{idx:02d}_{_safe_filename(str(result['title']), fallback=f'paper_{idx:02d}')}"
        content = build_review_report(result, query)
        (review_dir / filename).write_text(content, encoding="utf-8")
        papers_meta.append(
            {
                "rank": idx,
                "title": result["title"],
                "arxiv_url": result["arxiv_url"],
                "score": result.get("score"),
                "filename": filename,
            }
        )

    manifest = {
        "query": query.strip(),
        "created_at": created_at,
        "count": len(results),
        "papers": papers_meta,
    }
    (review_dir / "index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    top_index = _load_paper_reviews_index(project_id)
    top_index.append(
        {
            "folder": review_dir.name,
            "query": query.strip(),
            "created_at": created_at,
            "count": len(results),
            "path": f"{PAPER_REVIEWS_DIRNAME}/{review_dir.name}",
        }
    )
    _save_paper_reviews_index(project_id, top_index)

    return {
        "project_id": project_id,
        "query": query.strip(),
        "count": len(results),
        "folder": review_dir.name,
        "path": f"{PAPER_REVIEWS_DIRNAME}/{review_dir.name}",
        "papers": papers_meta,
    }
