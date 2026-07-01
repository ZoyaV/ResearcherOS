from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from koi.adapters.paths import agent_bundles_dir, paper_answers_dir, paper_reviews_dir
from koi.services.review.models import (
    PAPER_QA_BUNDLE_KIND,
    PAPER_REVIEW_BUNDLE_KIND,
    UNIVERSAL_AGENT_SPEC,
)
from koi.services.review.util import _normalize_text, _read_json

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


def _agent_bundle_dir(project_id: str, bundle_name: str) -> Path:
    return _repo_agent_bundles_root(project_id) / PAPER_REVIEW_BUNDLE_KIND / bundle_name


def _build_universal_prompt(manifest_rel_path: str) -> str:
    spec = UNIVERSAL_AGENT_SPEC
    lines = [
        f"# {spec.name}",
        "",
        "## Objective",
        "",
        spec.objective,
        "",
        "## Inputs",
        "",
    ]
    lines.extend(f"- {item}" for item in spec.inputs)
    lines.extend(
        [
            "",
            "## Outputs",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in spec.outputs)
    lines.extend(
        [
            "",
            "## Workflow",
            "",
        ]
    )
    lines.extend(f"1. {step}" for step in spec.workflow)
    lines.extend(
        [
            "",
            "## Rules",
            "",
        ]
    )
    lines.extend(f"- {rule}" for rule in spec.rules)
    lines.extend(
        [
            "",
            "## Environment Setup",
            "",
            "If you are using Codex CLI as the agent backend, make sure the `codex` binary is available in `PATH` before running the workflow.",
            "Recommended shell setup:",
            '```bash\nexport PATH="$PATH:/Users/Zemskova/.vscode/extensions/openai.chatgpt-26.609.30741-darwin-arm64/bin/macos-aarch64"\n```',
            "If KOI is started through `./scripts/koi-serve.sh`, ensure the same `PATH` is visible to that process or set `KOI_CODEX_BIN` explicitly in `.env`.",
            "",
            "## Working Contract",
            "",
            f"Read `{manifest_rel_path}` first.",
            "Use the manifest to locate paper summaries, cached text, and the cluster synthesis target.",
            "If you regenerate outputs, preserve the same filenames unless you have a clear reason to add a new versioned folder.",
            "When proposing research directions, phrase them as competing or complementary answers to the research question.",
            "",
            "## Expected Final Deliverable",
            "",
            "Return a concise research synthesis that identifies the main clusters, what each cluster assumes about dynamics, and what open gaps remain.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_surface_wrapper(surface_name: str, manifest_rel_path: str) -> str:
    return (
        f"# {surface_name} Wrapper\n\n"
        "Use the universal prompt as the primary instruction set.\n\n"
        f"1. Open `UNIVERSAL_PROMPT.md`.\n"
        f"2. Open `{manifest_rel_path}`.\n"
        "3. Follow the workflow without relying on chat-specific memory.\n"
        "4. Write or update markdown outputs in this review folder.\n\n"
        "Surface-specific note: keep the reasoning grounded in local files and make file edits explicit.\n"
    )


def _write_universal_agent_bundle(
    review_dir: Path,
    *,
    project_id: str,
    bundle_name: str,
    query: str,
    manifest: dict[str, object],
) -> None:
    bundle_dir = _agent_bundle_dir(project_id, bundle_name)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    bundle_manifest = {
        "bundle_kind": PAPER_REVIEW_BUNDLE_KIND,
        "agent": asdict(UNIVERSAL_AGENT_SPEC),
        "project_id": project_id,
        "query": query,
        "review_manifest": f"../../../projects/{project_id}/paper_reviews/{review_dir.name}/index.json",
        "cluster_report": f"../../../projects/{project_id}/paper_reviews/{review_dir.name}/{manifest['cluster_report']}",
        "paper_summaries": [
            f"../../../projects/{project_id}/paper_reviews/{review_dir.name}/{paper['summary_path']}"
            for paper in manifest["papers"]
        ],
        "paper_text_caches": [
            f"../../../projects/{project_id}/paper_reviews/{review_dir.name}/{paper['text_path']}"
            for paper in manifest["papers"]
            if paper.get("text_path")
        ],
        "paper_html_caches": [
            f"../../../projects/{project_id}/paper_reviews/{review_dir.name}/{paper['html_path']}"
            for paper in manifest["papers"]
            if paper.get("html_path")
        ],
        "paper_pdf_caches": [
            f"../../../projects/{project_id}/paper_reviews/{review_dir.name}/{paper['pdf_path']}"
            for paper in manifest["papers"]
            if paper.get("pdf_path")
        ],
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "UNIVERSAL_PROMPT.md").write_text(
        _build_universal_prompt("manifest.json"),
        encoding="utf-8",
    )
    (bundle_dir / "CURSOR.md").write_text(
        _build_surface_wrapper("Cursor", "manifest.json"),
        encoding="utf-8",
    )
    (bundle_dir / "CLAUDE.md").write_text(
        _build_surface_wrapper("Claude", "manifest.json"),
        encoding="utf-8",
    )
    (bundle_dir / "CODEX.md").write_text(
        _build_surface_wrapper("Codex", "manifest.json"),
        encoding="utf-8",
    )

