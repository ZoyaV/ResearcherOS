"""Dependency-boundary checks for the transitional KOI package layout."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("agent", "api", "examples", "hub", "koi", "scripts", "tests")
LEGACY_APPLICATION_MODULES = {
    "koi.application.live_queries",
    "koi.application.project_commands",
    "koi.application.project_views",
    "koi.application.report_commands",
}


def test_internal_code_uses_canonical_koi_imports() -> None:
    legacy_names = {
        path.stem
        for path in (ROOT / "koi").glob("*.py")
        if path.name != "__init__.py"
    }
    legacy_modules = {f"koi.{name}" for name in legacy_names}
    legacy_modules.update(LEGACY_APPLICATION_MODULES)
    violations: list[str] = []

    for directory in SOURCE_DIRS:
        for path in (ROOT / directory).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [node.module] if node.module else []
                    if node.module == "koi":
                        imported.extend(f"koi.{alias.name}" for alias in node.names)
                    elif node.module == "koi.application":
                        imported.extend(
                            f"koi.application.{alias.name}" for alias in node.names
                        )
                else:
                    continue

                for module in imported:
                    if module and any(
                        module == legacy or module.startswith(f"{legacy}.")
                        for legacy in legacy_modules
                    ):
                        relative = path.relative_to(ROOT)
                        violations.append(f"{relative}:{node.lineno}: {module}")

    assert not violations, (
        "Use canonical KOI package imports instead of compatibility modules:\n"
        + "\n".join(violations)
    )
