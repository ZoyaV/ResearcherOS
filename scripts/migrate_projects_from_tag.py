#!/usr/bin/env python3
"""Migrate KOI projects from hackaton_version tag into sibling-repo layout."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ENGINE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = ENGINE_ROOT.parent
TAG = "hackaton_version"

MIGRATIONS: list[dict] = [
    {
        "source": "projects/isaac-rl-bench",
        "target_dir": "isaac_harness",
        "frontmatter_patch": {
            "programs": [
                {"id": "isaac-harness", "title": "IsaacLab harness"},
            ],
            "code_root": "../../ReseachOS/examples/isaac_harness",
        },
        "body_replace": [
            (
                "из базы знаний kb/",
                "из базы знаний платформы (examples/isaac_harness/)",
            ),
        ],
    },
    {
        "source": "projects/isaaclab-dexsuite-reorient",
        "target_dir": "isaac_problem",
        "frontmatter_patch": {
            "programs": [
                {"id": "isaac-harness", "title": "IsaacLab harness"},
            ],
            "code_root": "../../koi-workspace/projects/IsaacLab_release_3_0",
            "description": (
                "Isaac Lab Dexsuite Reorient: baseline PPO и итерации идей train/eval. "
                "Код — koi-workspace/projects/IsaacLab_release_3_0 (git submodule)."
            ),
        },
        "body_replace": [
            (
                "в сабмодуле `projects/IsaacLab_release_3_0`",
                "в сабмодуле `koi-workspace/projects/IsaacLab_release_3_0`",
            ),
            (
                "Код — projects/IsaacLab_release_3_0 (git submodule).",
                "Код — koi-workspace/projects/IsaacLab_release_3_0 (git submodule).",
            ),
        ],
    },
    {
        "source": "projects/ai-agents-embodied",
        "target_dir": "mmrl_problem",
        "frontmatter_patch": {
            "programs": [
                {"id": "embodied-ai", "title": "Embodied AI agents"},
            ],
        },
        "body_replace": [],
    },
    {
        "source": "projects/embodied-ai-safety",
        "target_dir": "embodied_safety_problem",
        "frontmatter_patch": {
            "programs": [
                {"id": "embodied-ai", "title": "Embodied AI agents"},
            ],
        },
        "body_replace": [],
    },
]


def git_show(path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "show", f"{TAG}:{path}"],
        cwd=ENGINE_ROOT,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_list(prefix: str) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", TAG, "--", prefix],
        cwd=ENGINE_ROOT,
        capture_output=True,
        check=True,
    )
    return [p.decode("utf-8") for p in proc.stdout.split(b"\0") if p]


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = yaml.safe_load(parts[1]) or {}
    return meta, parts[2].lstrip("\n")


def merge_frontmatter(meta: dict, patch: dict) -> dict:
    out = dict(meta)
    for key, value in patch.items():
        out[key] = value
    return out


def patch_project_md(content: str, patch: dict, body_replace: list[tuple[str, str]]) -> str:
    meta, body = split_frontmatter(content)
    meta = merge_frontmatter(meta, patch)
    for old, new in body_replace:
        body = body.replace(old, new)
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm}\n---\n\n{body}"


def migrate_one(spec: dict) -> int:
    source = spec["source"]
    target_root = WORKSPACE_ROOT / spec["target_dir"]
    koi_root = target_root / "koi-structure"
    koi_root.mkdir(parents=True, exist_ok=True)

    files = git_list(source)
    if not files:
        print(f"skip {source}: no files in tag", file=sys.stderr)
        return 0

    written = 0
    prefix = source.rstrip("/") + "/"
    for rel in files:
        if not rel.startswith(prefix):
            continue
        inner = rel[len(prefix) :]
        dest = koi_root / inner
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = git_show(rel)
        if data is None:
            print(f"warn: missing {rel}", file=sys.stderr)
            continue
        if inner == "project.md":
            text = data.decode("utf-8")
            text = patch_project_md(
                text,
                spec.get("frontmatter_patch", {}),
                spec.get("body_replace", []),
            )
            dest.write_text(text, encoding="utf-8")
        else:
            dest.write_bytes(data)
        written += 1

    print(f"{spec['target_dir']}: {written} files from {source}")
    return written


def main() -> int:
    total = 0
    for spec in MIGRATIONS:
        total += migrate_one(spec)
    print(f"done: {total} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
