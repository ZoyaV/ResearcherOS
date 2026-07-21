"""Unit tests for Hub skills extraction (no GitHub / S3)."""

from __future__ import annotations

from pathlib import Path

from hub.app.skills import extract_skills, public_skills_for_publish, skill_to_entry


def _write_skill(root: Path, skill_id: str, *, visibility: str = "public", bad: bool = False) -> None:
    d = root / "skills" / skill_id
    d.mkdir(parents=True)
    if not bad:
        (d / "manifest.yaml").write_text(
            f"id: {skill_id}\n"
            f"title: Title {skill_id}\n"
            f"summary: A short summary\n"
            f"visibility: {visibility}\n",
            encoding="utf-8",
        )
        (d / "README.md").write_text(f"# {skill_id}\n\nBody.\n", encoding="utf-8")
        (d / "SKILL.md").write_text(f"# skill {skill_id}\n", encoding="utf-8")
    else:
        (d / "manifest.yaml").write_text("visibility: public\n", encoding="utf-8")
        # no README


def test_public_skills_only(tmp_path: Path) -> None:
    _write_skill(tmp_path, "alpha", visibility="public")
    _write_skill(tmp_path, "beta", visibility="private")
    _write_skill(tmp_path, "broken", bad=True)

    all_skills = extract_skills(tmp_path)
    assert len(all_skills) == 3
    assert {s.id for s in all_skills if s.ok} == {"alpha", "beta"}

    published = public_skills_for_publish(tmp_path)
    assert [s.id for s in published] == ["alpha"]

    entry = skill_to_entry(
        published[0],
        project_slug="demo-slug",
        project_title="Demo",
        owner_login="alice",
        repo_full_name="alice/repo",
        branch="koi/research",
        synced_at="2026-01-01T00:00:00Z",
    )
    assert entry["key"] == "demo-slug/alpha"
    assert entry["view_url"] == "/skills/demo-slug/alpha"
    assert entry["has_skill_md"] is True
    assert "Body." in entry["readme_md"]


def test_id_must_match_folder(tmp_path: Path) -> None:
    d = tmp_path / "skills" / "my-skill"
    d.mkdir(parents=True)
    (d / "manifest.yaml").write_text(
        "id: other-id\ntitle: X\nsummary: s\nvisibility: public\n",
        encoding="utf-8",
    )
    (d / "README.md").write_text("# x\n", encoding="utf-8")
    skills = extract_skills(tmp_path)
    assert len(skills) == 1
    assert skills[0].ok is False
    assert any("must match folder" in e for e in (skills[0].errors or []))
