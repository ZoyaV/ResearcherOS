"""Local CSV library, lexical ranking, and agent discovery."""

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
from koi.literature.naming import normalize_spaces, safe_filename, slugify

_ws = get_workspace()
LIBRARY_UPLOAD_PATH = _ws.library_upload
LIBRARY_CSV_CANDIDATES = _ws.library_csv_candidates()
PAPER_REVIEWS_DIRNAME = "paper_reviews"
LIBRARY_REQUIRED_FIELDS = ("no", "arxiv_url", "title", "authors", "abstract")
LIBRARY_FIELDNAMES = ("no", "arxiv_url", "title", "authors", "abstract")

TOKEN_RE = re.compile(r"[a-z0-9\u0400-\u04ff]+")
ARXIV_TOKEN_RE = re.compile(r"[a-z0-9\u0400-\u04ff]+(?:-[a-z0-9]+)?")
CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
ARXIV_YEAR_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf|html)/)?(\d{2})(\d{2})\.\d{4,5}",
    re.IGNORECASE,
)
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

# Too broad for arXiv; without domain terms they attract irrelevant papers.
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
    return normalize_spaces(text)


def _slugify(text: str, fallback: str = "review") -> str:
    return slugify(text, fallback)


def _safe_filename(text: str, fallback: str = "paper") -> str:
    return safe_filename(text, fallback)


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


def infer_year_from_arxiv_url(arxiv_url: str) -> int | None:
    match = ARXIV_YEAR_RE.search(arxiv_url or "")
    if not match:
        return None
    yy = int(match.group(1))
    mm = int(match.group(2))
    if mm < 1 or mm > 12:
        return None
    return 2000 + yy


def list_library_papers(*, limit: int | None = None) -> list[dict[str, object]]:
    """Return papers from the local CSV library for the literature sidebar."""
    if not library_csv_exists():
        return []
    try:
        library_csv = resolve_library_csv()
    except FileNotFoundError:
        return []

    papers: list[dict[str, object]] = []
    with library_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            title = _normalize_spaces(row.get("title", ""))
            arxiv_url = _normalize_spaces(row.get("arxiv_url", ""))
            if not title or not arxiv_url:
                continue
            authors = _normalize_spaces(row.get("authors", ""))
            abstract = _normalize_spaces(row.get("abstract", ""))
            preview = abstract
            if len(preview) > 280:
                preview = preview[:279].rstrip() + "…"
            papers.append(
                {
                    "title": title,
                    "arxiv_url": arxiv_url,
                    "authors": authors,
                    "year": infer_year_from_arxiv_url(arxiv_url),
                    "abstract": abstract,
                    "abstract_preview": preview,
                }
            )
            if limit is not None and len(papers) >= max(1, limit):
                break
    return papers


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
        return get_workspace().relative_to_engine(path)
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
    response, backend = run_agent(prompt, cwd=get_workspace().agent_cwd(), timeout=180)
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
