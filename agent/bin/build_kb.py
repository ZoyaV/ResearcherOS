#!/usr/bin/env python3
"""Пересборка баз знаний из KOI-проектов.

Архитектура (per-project, встроена в ядро):
  • у КАЖДОГО проекта своя база знаний `projects/<id>/KNOWLEDGE.md` —
    канонический рендер из `koi/knowledge.py` (дерево + вердикты + инсайты).
    Она же пишется автоматически при любом `save_project()`.
  • `agent/KNOWLEDGE.md` — тонкий ГЛОБАЛЬНЫЙ индекс: одна строка на проект со сводкой
    и ссылкой на его базу знаний. Содержимое проектов тут НЕ дублируется.

Обе вещи — производные, руками не правят, перегенерируются:

    python agent/bin/build_kb.py

Источник правды — `projects/<id>/project.md` (вердикты) и `research.json` (инсайты).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from koi.services.knowledge import VERDICT_MARK, write_project_knowledge  # noqa: E402
from koi.core.models import NodeType, Verdict  # noqa: E402
from koi.laboratory.programs import list_programs, program_summary  # noqa: E402
from koi.adapters.repository import list_projects, load_project  # noqa: E402

GLOBAL_INDEX = ROOT / "kb" / "KNOWLEDGE.md"


def _methods_under(nodes, cause_id):
    out = []
    for mid in (n for n in nodes if n.parent_id == cause_id):
        out += [m for m in nodes if m.parent_id == mid.id and m.node_type == NodeType.METHOD]
    return out


def build_global_index() -> tuple[str, int, int]:
    """Тонкий индекс по проектам. Возвращает (markdown, n_projects, n_insights)."""
    rows: list[str] = []
    total_insights = 0
    projects = list_projects()

    for meta in projects:
        pid = meta["id"]
        project = load_project(pid)  # save_project-хук уже обновил per-project KNOWLEDGE.md
        if project is None:
            continue
        # ...но пересоберём явно, чтобы build_kb был самодостаточным
        write_project_knowledge(project)
        nodes = project.nodes
        causes = [n for n in nodes if n.node_type == NodeType.CAUSE]
        supported = sum(1 for c in causes if c.verdict == Verdict.SUPPORTED)
        refuted = sum(1 for c in causes if c.verdict == Verdict.REFUTED)
        insights = sum(len(m.research_questions) for c in causes for m in _methods_under(nodes, c.id))
        total_insights += insights
        rows.append(
            f"| [{project.title}](../projects/{pid}/KNOWLEDGE.md) | `{pid}` | "
            f"{len(causes)} | {supported} | {refuted} | {insights} |"
        )

    program_sections: list[str] = []
    for program in list_programs():
        summary = program_summary(program["id"])
        if summary is None or not summary.get("project_stats"):
            continue
        prog_rows = [
            f"| [{s['title']}](../projects/{s['id']}/KNOWLEDGE.md) | `{s['id']}` | "
            f"{s['hypotheses']} | {s['supported']} | {s['refuted']} | {s['insights']} |"
            for s in summary["project_stats"]
        ]
        totals = summary["totals"]
        program_sections.extend(
            [
                f"## {program['title']}",
                "",
                f"Программа `{program['id']}` · проектов: {totals['projects']} · "
                f"инсайтов: {totals['insights']}",
                "",
                "| Проект | id | гипотез | ✔ подтв. | ✗ опров. | инсайтов |",
                "| --- | --- | --- | --- | --- | --- |",
                *prog_rows,
                "",
            ]
        )

    lines = [
        "# KNOWLEDGE.md — глобальный индекс баз знаний",
        "",
        "Сгенерировано `agent/bin/build_kb.py`. У каждого проекта своя база знаний",
        "`projects/<id>/KNOWLEDGE.md` (канонический рендер `koi/knowledge.py`); здесь —",
        "только сводка и ссылки. Руками не править — перегенерировать командой выше.",
        "",
        f"Проектов: {len(rows)} · инсайтов всего: {total_insights}",
        "",
        "## Все проекты",
        "",
        "| Проект | id | гипотез | ✔ подтв. | ✗ опров. | инсайтов |",
        "| --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
        "## По программам",
        "",
        *program_sections,
        "## Условные обозначения вердиктов",
        "",
        *[f"- {mark}" for mark in VERDICT_MARK.values()],
        "",
    ]
    return "\n".join(lines).rstrip() + "\n", len(rows), total_insights


def main() -> None:
    md, n_projects, n_insights = build_global_index()
    GLOBAL_INDEX.write_text(md, encoding="utf-8")
    print(f"wrote {GLOBAL_INDEX}  ({n_projects} projects, {n_insights} insights)")
    print("per-project: projects/<id>/KNOWLEDGE.md обновлены")


if __name__ == "__main__":
    main()
