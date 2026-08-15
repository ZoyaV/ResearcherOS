"""Bidirectional CRDT ↔ filesystem bridge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from koi.paper.collaboration.document import CollabDocument
from koi.paper.collaboration.materializer import atomic_write_text
from koi.paper.collaboration.revisions import content_hash
from koi.paper.collaboration.text_ops import MergeResult


@dataclass
class MaterializeResult:
    revision: int
    content_hash: str
    path: str
    wrote: bool


class FilesystemBridge:
    def __init__(self, document: CollabDocument, tex_path: Path) -> None:
        self.document = document
        self.tex_path = tex_path
        self.last_hash = content_hash(document.to_string())
        self.last_revision = document.revision
        self.last_mtime: float | None = None
        self.last_mtime_ns: int | None = None

    def materialize(self) -> MaterializeResult:
        text = self.document.to_string()
        digest = content_hash(text)
        on_disk = self.read_file()
        if on_disk is not None and content_hash(on_disk) == digest:
            self.last_hash = digest
            self.last_revision = self.document.revision
            try:
                stat = self.tex_path.stat()
                self.last_mtime = stat.st_mtime
                self.last_mtime_ns = stat.st_mtime_ns
            except OSError:
                pass
            return MaterializeResult(
                revision=self.document.revision,
                content_hash=digest,
                path=str(self.tex_path),
                wrote=False,
            )
        atomic_write_text(self.tex_path, text)
        self.last_hash = digest
        self.last_revision = self.document.revision
        try:
            stat = self.tex_path.stat()
            self.last_mtime = stat.st_mtime
            self.last_mtime_ns = stat.st_mtime_ns
        except OSError:
            self.last_mtime = None
            self.last_mtime_ns = None
        self.document.log.write_sidecar(self.tex_path.parent)
        return MaterializeResult(
            revision=self.document.revision,
            content_hash=digest,
            path=str(self.tex_path),
            wrote=True,
        )

    def read_file(self) -> str | None:
        if not self.tex_path.is_file():
            return None
        return self.tex_path.read_text(encoding="utf-8")

    def is_own_materialization(self, file_text: str | None = None) -> bool:
        text = file_text if file_text is not None else self.read_file()
        if text is None:
            return False
        return content_hash(text) == self.last_hash

    def import_file(
        self,
        *,
        base_text: str | None = None,
        file_text: str | None = None,
    ) -> MergeResult:
        incoming = file_text if file_text is not None else self.read_file()
        if incoming is None:
            return MergeResult(ok=True, text=self.document.to_string(), changed=False)
        if self.is_own_materialization(incoming):
            return MergeResult(ok=True, text=self.document.to_string(), changed=False)
        base = base_text if base_text is not None else self.document.log.text_at(self.last_revision)
        if base is None:
            base = self.document.to_string()
        result = self.document.import_from_base(base, incoming)
        if result.ok and result.changed:
            on_disk = self.read_file()
            if on_disk is not None and on_disk == result.text:
                self.last_hash = content_hash(result.text)
                self.last_revision = self.document.revision
                try:
                    stat = self.tex_path.stat()
                    self.last_mtime = stat.st_mtime
                    self.last_mtime_ns = stat.st_mtime_ns
                except OSError:
                    pass
        return result
