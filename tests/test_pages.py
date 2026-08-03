"""Unit tests for master HTML pages store."""

from __future__ import annotations

from pathlib import Path

import pytest

from koi.adapters import pages as pages_store


@pytest.fixture()
def project_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "koi-structure"
    root.mkdir()

    def fake_pages_dir(project_id: str) -> Path:
        d = root / "pages"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(pages_store, "project_pages_dir", fake_pages_dir)
    # pages_dir() in module wraps project_pages_dir — patch the imported name used inside
    monkeypatch.setattr(
        "koi.adapters.paths.pages_dir",
        lambda project_id: fake_pages_dir(project_id),
    )
    return "demo"


def test_create_attach_visibility_and_pins(project_pages: str) -> None:
    page = pages_store.create_page(project_pages, "Overview")
    assert page["slug"]
    assert (pages_store.pages_dir(project_pages) / page["slug"] / "index.html").is_file()

    attached = pages_store.attach_page(project_pages, "node-1", page["id"])
    assert len(attached) == 1
    assert attached[0]["visible"] is False
    assert pages_store.visible_pins(project_pages) == {}

    visible = pages_store.set_page_visible(project_pages, "node-1", page["id"], True)
    assert visible[0]["visible"] is True
    pins = pages_store.visible_pins(project_pages)
    assert pins["node-1"][0]["id"] == page["id"]
    assert pins["node-1"][0]["title"] == "Overview"


def test_discover_orphan_html_folder(project_pages: str) -> None:
    folder = pages_store.pages_dir(project_pages) / "dropped-report"
    folder.mkdir()
    (folder / "index.html").write_text(
        "<html><title>Dropped</title><body><h1>Hi</h1></body></html>",
        encoding="utf-8",
    )
    pages = pages_store.list_pages(project_pages)
    assert any(p["slug"] == "dropped-report" and p["title"] == "Dropped" for p in pages)
