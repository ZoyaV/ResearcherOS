from __future__ import annotations

import re
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from koi.services.review.models import MAX_HTML_CHARS, MAX_TEXT_CHARS
from koi.services.review.util import _normalize_text

class _ArxivHTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "math"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in {"p", "div", "section", "article", "li", "ul", "ol", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "math"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"p", "div", "section", "article", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = unescape(data)
        if text.strip():
            self._chunks.append(text)

    def get_text(self) -> str:
        lines = [_normalize_text(line) for line in "\n".join(self._chunks).splitlines()]
        cleaned = [line for line in lines if line]
        return "\n\n".join(cleaned)



def extract_arxiv_id(arxiv_url: str) -> str:
    cleaned = arxiv_url.strip().replace("http://", "https://")
    cleaned = cleaned.rstrip("/")
    if "/abs/" in cleaned:
        cleaned = cleaned.split("/abs/", 1)[1]
    cleaned = re.sub(r"v\d+$", "", cleaned)
    return cleaned


def infer_year_from_arxiv_id(arxiv_id: str) -> int | None:
    match = re.match(r"^(\d{2})(\d{2})\.\d{4,5}$", arxiv_id)
    if not match:
        return None
    yy = int(match.group(1))
    mm = int(match.group(2))
    if mm < 1 or mm > 12:
        return None
    return 2000 + yy


def fetch_arxiv_pdf(arxiv_id: str, destination: Path, force_refresh: bool = False) -> Path | None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force_refresh:
        return destination
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            destination.write_bytes(response.read())
        return destination
    except Exception:
        if destination.exists():
            destination.unlink()
        return None


def fetch_arxiv_html(arxiv_id: str, destination: Path, force_refresh: bool = False) -> Path | None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force_refresh:
        return destination
    url = f"https://arxiv.org/html/{arxiv_id}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            destination.write_bytes(response.read())
        return destination
    except Exception:
        if destination.exists():
            destination.unlink()
        return None


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""


def extract_arxiv_html_text(html_path: Path) -> str:
    try:
        raw = html_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    parser = _ArxivHTMLTextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        return ""

    text = parser.get_text()
    if not text:
        return ""
    compact = text[:MAX_HTML_CHARS]
    return compact.strip()

    try:
        reader = PdfReader(str(pdf_path))
        chunks: list[str] = []
        total = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if not page_text:
                continue
            page_text = _normalize_text(page_text)
            if not page_text:
                continue
            remaining = MAX_TEXT_CHARS - total
            if remaining <= 0:
                break
            excerpt = page_text[:remaining]
            chunks.append(excerpt)
            total += len(excerpt)
        return "\n\n".join(chunks)
    except Exception:
        return ""
