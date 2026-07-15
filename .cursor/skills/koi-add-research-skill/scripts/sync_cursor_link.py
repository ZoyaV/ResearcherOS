#!/usr/bin/env python3
"""Validate a canonical ResearchOS skill and optionally expose it to Cursor."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _frontmatter_name(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(?P<header>.*?)\n---(?:\n|$)", text, re.DOTALL)
    if match is None:
        raise SystemExit(f"Missing YAML frontmatter: {skill_file}")
    name_match = re.search(r"^name:\s*([^\n]+)$", match.group("header"), re.MULTILINE)
    if name_match is None:
        raise SystemExit(f"Missing frontmatter name: {skill_file}")
    return name_match.group(1).strip().strip('"\'')


def validate_canonical_skill(skill_name: str) -> Path:
    if not NAME_RE.fullmatch(skill_name):
        raise SystemExit("Skill name must contain lowercase letters, digits, and hyphens only")
    skill_dir = ROOT / "agents" / "skills" / skill_name
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise SystemExit(f"Canonical research skill not found: {skill_file}")
    declared_name = _frontmatter_name(skill_file)
    if declared_name != skill_name:
        raise SystemExit(
            f"Skill name mismatch: folder={skill_name!r}, frontmatter={declared_name!r}"
        )
    return skill_dir


def validate_cursor_link(skill_name: str, *, create: bool) -> Path | None:
    link = ROOT / ".cursor" / "skills" / skill_name
    expected = Path("../../agents/skills") / skill_name
    if not link.exists() and not link.is_symlink():
        if not create:
            return None
        link.symlink_to(expected, target_is_directory=True)
    if not link.is_symlink():
        raise SystemExit(f"Cursor path exists but is not a symlink: {link}")
    actual = Path(link.readlink())
    if actual != expected:
        raise SystemExit(f"Wrong Cursor link: {link} -> {actual}; expected {expected}")
    if not link.resolve().is_dir():
        raise SystemExit(f"Broken Cursor link: {link}")
    return link


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_name")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create", action="store_true", help="Create the Cursor symlink")
    mode.add_argument("--check", action="store_true", help="Validate without creating a link")
    args = parser.parse_args()

    skill_dir = validate_canonical_skill(args.skill_name)
    link = validate_cursor_link(args.skill_name, create=args.create)
    print(f"canonical: {skill_dir.relative_to(ROOT)}")
    print(f"cursor: {link.relative_to(ROOT) if link else 'not exposed'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
