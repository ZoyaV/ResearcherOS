"""Yrs-backed collaborative text document.

The live session authority is a pycrdt ``Text`` named ``content`` so Spike B
can exchange binary Yjs/Yrs updates without changing the document model.
"""

from __future__ import annotations

from pycrdt import Doc, Text

from koi.paper.collaboration.revisions import RevisionLog, content_hash
from koi.paper.collaboration.text_ops import MergeResult, import_relative, prefix_suffix_span


CONTENT_KEY = "content"


class CollabDocument:
    def __init__(self, initial: str = "", *, document_id: str = "") -> None:
        self.doc = Doc()
        self.text: Text = self.doc.get(CONTENT_KEY, type=Text)
        if initial:
            self.text.insert(0, initial)
        self.revision = 0
        self.log = RevisionLog(document_id=document_id)
        self.log.remember(0, initial)

    def to_string(self) -> str:
        return str(self.text)

    def content_hash(self) -> str:
        return content_hash(self.to_string())

    def snapshot(self) -> str:
        return self.to_string()

    def replace_with(self, new_text: str) -> bool:
        current = self.to_string()
        if current == new_text:
            return False
        span = prefix_suffix_span(current, new_text)
        self._apply_span(span.start, span.delete_len, span.new_text)
        self._bump(new_text)
        return True

    def apply_edit(self, start: int, delete_len: int, insert: str) -> str:
        current = self.to_string()
        start = max(0, min(start, len(current)))
        delete_len = max(0, min(delete_len, len(current) - start))
        self._apply_span(start, delete_len, insert)
        text = self.to_string()
        self._bump(text)
        return text

    def import_from_base(self, base: str, incoming: str) -> MergeResult:
        current = self.to_string()
        result = import_relative(base, current, incoming)
        if result.ok and result.changed:
            self.replace_with(result.text)
        return result

    def get_state(self) -> bytes:
        return self.doc.get_state()

    def get_update(self, state: bytes | None = None) -> bytes:
        return self.doc.get_update(state)

    def apply_update(self, update: bytes) -> str:
        self.doc.apply_update(update)
        text = self.to_string()
        self._bump(text)
        return text

    def _apply_span(self, start: int, delete_len: int, insert: str) -> None:
        # pycrdt's Python Text API addresses UTF-8 byte offsets, while all
        # collaboration spans are ordinary Python character offsets. Passing
        # character offsets directly corrupts edits after non-ASCII LaTeX.
        current = self.to_string()
        byte_start = len(current[:start].encode("utf-8"))
        byte_end = len(current[: start + delete_len].encode("utf-8"))
        if delete_len:
            del self.text[byte_start:byte_end]
        if insert:
            self.text.insert(byte_start, insert)

    def _bump(self, text: str) -> None:
        self.revision += 1
        self.log.remember(self.revision, text)
