"""Materialize Evo state as a live ResearchOS text/artifact stream."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from koi.adapters import card_reports, repository
from koi.adapters.paths import repo_root


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _report_dir(project_id: str, board_id: str, card_id: str, title: str) -> Path:
    project = repository.load_project(project_id, sync_reports=False)
    if project is None:
        raise LookupError(f"Project not found: {project_id}")
    report = card_reports.resolve_card_report_path(
        project_id,
        project,
        next(b for b in project.boards if b.id == board_id),
        next(c for b in project.boards for c in b.cards if c.id == card_id),
    )
    if report is None:
        report = card_reports.ensure_card_report(project, board_id, card_id, title)
    report.parent.mkdir(parents=True, exist_ok=True)
    return report.parent


def _nodes(run_root: Path) -> list[dict[str, Any]]:
    graph = _load_json(run_root / "graph.json", {})
    return [
        dict(node)
        for node in (graph.get("nodes") or {}).values()
        if isinstance(node, dict) and node.get("id") != "root"
    ]


def _checks(run_root: Path, exp_id: str) -> list[dict[str, Any]]:
    root = run_root / "experiments" / exp_id / "checks"
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for path in sorted(root.iterdir()):
        check = _load_json(path / "check.json", None)
        if isinstance(check, dict):
            out.append(check)
        gate = _load_json(path / "gate_check.json", None)
        if isinstance(gate, dict):
            out.append(gate)
    return out


def _node_summary(nodes: list[dict[str, Any]], checks: list[dict[str, Any]]) -> tuple[str, str]:
    """Return user-facing idea and solution without changing Evo's graph."""
    if not nodes:
        return "Ожидание первой candidate-ветки.", "Решение ещё не предложено."
    passed = [item for item in checks if item.get("status") == "passed"]
    score = max((item.get("score") for item in checks if isinstance(item.get("score"), (int, float))), default=None)
    latest = sorted(nodes, key=lambda node: str(node.get("updated_at") or ""))[-1]
    score_by_exp = {}
    for item in checks:
        if isinstance(item.get("score"), (int, float)):
            exp_id = str(item.get("experiment_id") or "")
            score_by_exp[exp_id] = max(score_by_exp.get(exp_id, float("-inf")), float(item["score"]))
    best = max(nodes, key=lambda node: (score_by_exp.get(str(node.get("id") or ""), float("-inf")), node.get("status") != "pending"), default=latest)
    idea = str(latest.get("hypothesis") or "Evo исследует candidate-ветку.")
    solution = f"Лучший кандидат `{best.get('id')}`; статус `{best.get('status', 'unknown')}`"
    if score is not None:
        solution += f"; score `{score}`"
    if passed:
        solution += f"; пройдено проверок: `{len(passed)}`"
    return idea, solution


def _copy_artifacts(nodes: list[dict[str, Any]], report_dir: Path, run_root: Path) -> list[str]:
    assets_dir = report_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    sources: list[Path] = []
    for node in nodes:
        worktree = Path(str(node.get("worktree") or ""))
        for base in (worktree / "runs", worktree / "datasets", worktree / "artifacts"):
            if not base.is_dir():
                continue
            sources.extend(
                child for child in base.rglob("*")
                if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES
            )
    for base in (run_root.parent.parent / "runs", run_root / "runs"):
        if base.is_dir():
            sources.extend(child for child in base.rglob("*") if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES)
    copied: list[str] = []
    for source in sorted(sources, key=str)[:24]:
        target = assets_dir / f"evo-{source.name}"
        try:
            shutil.copy2(source, target)
        except OSError:
            continue
        copied.append(f"assets/{target.name}")
    return copied


def sync_live_report(
    project_id: str,
    board_id: str,
    card_id: str,
    card_title: str,
    run_path: str,
) -> dict[str, Any]:
    """Write ``evo-live.md`` and copy graphs for one ResearchOS card."""
    # Evo's native workspace is created at the ResearchOS repository root;
    # ``code_root`` may intentionally point at a shared parent for datasets.
    root = (repo_root(project_id) / run_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    nodes = _nodes(root)
    report_dir = _report_dir(project_id, board_id, card_id, card_title)
    copied = _copy_artifacts(nodes, report_dir, root)
    checks = [check for node in nodes for check in _checks(root, str(node.get("id") or ""))]
    idea, solution = _node_summary(nodes, checks)
    annotations = _load_json(root / "annotations.json", {})
    lines = [
        "# Evo live stream",
        "",
        f"> Обновлено: {datetime.now(timezone.utc).isoformat()}",
        "> Это рабочий поток Evo, не финальный научный verdict.",
        "",
        "## Идеи Evo",
        "",
        f"**Текущая идея:** {idea}",
        "",
    ]
    if not nodes:
        lines.append("Пока нет candidate-веток.")
    for node in nodes:
        lines.extend(
            [
                f"### `{node.get('id', '')}` — {node.get('hypothesis') or 'без hypothesis'}",
                f"- Статус: `{node.get('status')}`",
                f"- Ветка: `{node.get('branch') or '—'}`",
                f"- Score: `{node.get('score') if node.get('score') is not None else '—'}`",
                f"- Worktree: `{node.get('worktree') or '—'}`",
                "",
            ]
        )
    lines += ["## Решения и проверки", "", f"**Текущий кандидат:** {solution}", ""]
    if not checks:
        lines.append("Проверки ещё не записаны.")
    for check in checks:
        lines.append(
            f"- `{check.get('experiment_id', 'experiment')}`: **{check.get('status', 'unknown')}**; "
            f"score `{check.get('score') if check.get('score') is not None else '—'}`"
        )
    lines += ["", "## Заметки Evo", ""]
    raw_annotations = annotations.get("annotations") if isinstance(annotations, dict) else []
    if raw_annotations:
        lines.extend(f"- {item}" for item in raw_annotations)
    else:
        lines.append("Заметок пока нет.")
    lines += ["", "## Графики и артефакты", ""]
    if copied:
        lines.extend(f"- ![{Path(path).name}]({path})" for path in copied)
    else:
        lines.append("Графики ещё не опубликованы benchmark-ом.")
    live_path = report_dir / "evo-live.md"
    live_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "path": str(live_path),
        "nodes": len(nodes),
        "checks": len(checks),
        "artifacts": copied,
    }
