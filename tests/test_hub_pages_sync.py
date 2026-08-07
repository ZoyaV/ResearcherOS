"""Hub sync of master HTML pages (map pins + file serve)."""

from __future__ import annotations

from pathlib import Path

from hub.app.config import HubConfig
from hub.app.koi_loader import project_snapshot
from hub.app.store import HubStore


def _koi_with_visible_page(root: Path) -> str:
    root.mkdir(parents=True)
    (root / "project.md").write_text(
        """---
id: demo-pages
title: Demo Pages
---
# problem: root

Root

#### method: m1

Method
""",
        encoding="utf-8",
    )
    pages = root / "pages"
    pages.mkdir()
    (pages / "overview").mkdir()
    (pages / "overview" / "index.html").write_text(
        "<html><title>Overview</title><body><h1>Hi</h1></body></html>",
        encoding="utf-8",
    )
    page_id = "page-overview-1"
    (pages / "index.json").write_text(
        f"""{{
  "version": 1,
  "pages": {{
    "{page_id}": {{
      "id": "{page_id}",
      "title": "Overview",
      "slug": "overview",
      "entry": "index.html"
    }}
  }},
  "attachments": {{
    "m1": [{{"page_id": "{page_id}", "visible": true}}]
  }}
}}
""",
        encoding="utf-8",
    )
    return page_id


def test_project_snapshot_reads_page_pins_from_koi_root(tmp_path: Path) -> None:
    koi = tmp_path / "koi-structure"
    page_id = _koi_with_visible_page(koi)
    snap = project_snapshot(koi)
    assert snap is not None
    assert snap["page_pins"]["m1"][0]["id"] == page_id
    assert snap["page_pins"]["m1"][0]["title"] == "Overview"


def test_hub_store_save_and_resolve_page_file(tmp_path: Path) -> None:
    koi = tmp_path / "koi-structure"
    page_id = _koi_with_visible_page(koi)
    config = HubConfig(
        public_url="http://127.0.0.1:8020",
        github_client_id="",
        github_client_secret="",
        session_secret="test",
        data_dir=tmp_path / "hub-data",
        s3_bucket="",
        s3_endpoint="",
        s3_access_key="",
        s3_secret_key="",
        default_branch="koi/research",
        koi_path="koi-structure",
    )
    store = HubStore(config)
    count = store.save_pages_tree("demo", koi / "pages")
    assert count >= 2
    path = store.resolve_page_file("demo", page_id, "index.html")
    assert path is not None
    assert path.is_file()
    assert "Hi" in path.read_text(encoding="utf-8")
    assert store.resolve_page_file("demo", "missing", "index.html") is None


def test_hub_composite_merges_page_pins_from_member_snapshots() -> None:
    from hub.app.hub_composite import load_hub_composite
    from types import SimpleNamespace

    problem = "Shared problem"
    a = {
        "id": "proj-a",
        "title": "A",
        "description": "",
        "literature_keywords": [],
        "card_tags": [],
        "nodes": [
            {
                "id": "problem",
                "project_id": "proj-a",
                "parent_id": None,
                "node_type": "problem",
                "title": problem,
                "description": "",
                "verdict": "open",
                "research_questions": [],
            }
        ],
        "boards": {},
        "page_pins": {
            "problem": [{"id": "p-a", "title": "Report A"}],
        },
    }
    b = {
        "id": "proj-b",
        "title": "B",
        "description": "",
        "literature_keywords": [],
        "card_tags": [],
        "nodes": [
            {
                "id": "problem",
                "project_id": "proj-b",
                "parent_id": None,
                "node_type": "problem",
                "title": problem,
                "description": "",
                "verdict": "open",
                "research_questions": [],
            }
        ],
        "boards": {},
        "page_pins": {
            "problem": [{"id": "p-b", "title": "Report B"}],
        },
    }
    members = [
        (SimpleNamespace(slug="a", title="a", composite_id="shared", programs=[]), a),
        (SimpleNamespace(slug="b", title="b", composite_id="shared", programs=[]), b),
    ]
    payload = load_hub_composite(store=None, composite_id="shared", members=members)
    assert payload is not None
    pins = payload["page_pins"]["problem"]
    by_id = {p["id"]: p for p in pins}
    assert by_id["p-a"]["project_id"] == "proj-a"
    assert by_id["p-b"]["project_id"] == "proj-b"
