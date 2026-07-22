"""Import-smoke checks for Cursor hooks without executing their main functions."""

import runpy
from pathlib import Path

import pytest

from koi.adapters.hooks_paths import koi_root_from_hook


ROOT = Path(__file__).resolve().parents[1]
CONTENT_SKILLS = (
    "koi-agent-chat",
    "koi-done-research",
    "koi-execute-card",
    "koi-knowledge-curator",
    "koi-paper",
    "koi-project-sync",
    "koi-prose-style",
    "koi-related-work",
    "koi-report-review",
)


@pytest.mark.parametrize(
    "relative_path",
    (
        "agents/skills/koi-agent-chat/hooks/koi-agent-chat-hook.py",
        "agents/skills/koi-done-research/hooks/koi-done-research-hook.py",
        "agents/skills/koi-project-sync/hooks/koi-project-sync-hook.py",
    ),
)
def test_cursor_hook_imports(relative_path: str) -> None:
    path = ROOT / relative_path
    assert path.is_file()
    assert koi_root_from_hook(path) == ROOT
    namespace = runpy.run_path(str(path), run_name="cursor_hook_smoke")
    assert callable(namespace["main"])


@pytest.mark.parametrize("skill_name", CONTENT_SKILLS)
def test_cursor_content_skill_links_to_canonical_skill(skill_name: str) -> None:
    cursor_skill = ROOT / ".cursor" / "skills" / skill_name
    canonical_skill = ROOT / "agents" / "skills" / skill_name

    if not cursor_skill.exists() and not cursor_skill.is_symlink():
        pytest.skip("local Cursor skill link not installed")
    assert cursor_skill.is_symlink()
    assert cursor_skill.resolve() == canonical_skill.resolve()
    assert (cursor_skill / "SKILL.md").is_file()


def test_report_skill_owns_its_templates() -> None:
    skill = ROOT / "agents" / "skills" / "koi-report-review"

    for name in ("experiment-report.md", "report-rules.md", "report-skeleton.md"):
        assert (skill / name).is_file()


def test_cursor_hooks_template_points_at_agents_hooks() -> None:
    template = (ROOT / "agents" / "cursor-hooks.json").read_text(encoding="utf-8")
    assert "agents/skills/koi-agent-chat/hooks/" in template
    assert "agents/hooks/koi-session-start.sh" in template
    assert ".cursor/hooks/" not in template
    assert "researchos-channel-news" not in template


def test_research_skills_catalog_excludes_product_devtools() -> None:
    names = {p.name for p in (ROOT / "agents" / "skills").iterdir() if p.is_dir()}
    assert "researchos-channel-news" not in names
    assert "literature-cluster-orchestrator" in names
    assert "koi-related-work" in names
