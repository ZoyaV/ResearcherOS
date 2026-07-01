#!/usr/bin/env python3
"""Самотест конвейера «отчёт агента → автоинтеграция → база знаний».

Создаёт одноразовый проект `kb-selftest`, прогоняет настоящие код-пути
(save_project-хук БЗ, report_ingest, koi_check_hypothesis со стаб-бинарём
вместо Claude Code CLI) и в конце удаляет ВСЁ, что создал
(projects/kb-selftest/ и временный стаб). Запуск из корня репо:

    PYTHONPATH=. python scripts/test_kb_pipeline.py
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from koi.models import (  # noqa: E402
    DEFAULT_KANBAN_COLUMNS,
    ExperimentCard,
    KanbanBoard,
    Node,
    NodeType,
    Project,
    Verdict,
)
from koi.report_ingest import expected_run_report_path, ingest_report  # noqa: E402
from koi.adapters.paths import koi_root
from koi.adapters.project_mount import get_mount, rescan_projects
from koi.repository import create_project, load_project, save_project  # noqa: E402

PID = "kb-selftest"


def project_dir() -> Path:
    return koi_root(PID)

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def make_project() -> Project:
    nodes = [
        Node(id="p-root", project_id=PID, parent_id=None, node_type=NodeType.PROBLEM,
             title="Самотест конвейера БЗ",
             description="Синтетический проект для проверки автоинтеграции; удаляется тестом."),
        Node(id="c-test", project_id=PID, parent_id="p-root", node_type=NodeType.CAUSE,
             title="Тестовая гипотеза: парсер чисел работает",
             description="Правило решения: supported если 2+2=4; refuted иначе."),
        Node(id="ev-test", project_id=PID, parent_id="c-test",
             node_type=NodeType.CAUSE_EVIDENCE,
             title="Арифметическая проверка", description=""),
        Node(id="m-test", project_id=PID, parent_id="ev-test", node_type=NodeType.METHOD,
             title="Прямое вычисление", description="Вычислить 2+2 и сравнить с 4."),
        Node(id="c-test2", project_id=PID, parent_id="p-root", node_type=NodeType.CAUSE,
             title="Вторая гипотеза: для стаб-агента",
             description="Правило решения: supported если стаб-агент записал отчёт."),
        Node(id="ev-test2", project_id=PID, parent_id="c-test2",
             node_type=NodeType.CAUSE_EVIDENCE,
             title="Проверка стаб-агентом", description=""),
        Node(id="m-test2", project_id=PID, parent_id="ev-test2", node_type=NodeType.METHOD,
             title="Стаб-прогон", description="Отчёт пишет стаб вместо Claude CLI."),
    ]
    boards = [
        KanbanBoard(id="board-m-test", owner_node_id="m-test",
                    columns=list(DEFAULT_KANBAN_COLUMNS),
                    cards=[ExperimentCard(id="card-arith", board_id="board-m-test",
                                          column_id="running",
                                          title="Проверка 2+2")]),
        KanbanBoard(id="board-m-test2", owner_node_id="m-test2",
                    columns=list(DEFAULT_KANBAN_COLUMNS),
                    cards=[ExperimentCard(id="card-stub", board_id="board-m-test2",
                                          column_id="backlog",
                                          title="Стаб-проверка")]),
    ]
    return Project(id=PID, title="Самотест конвейера БЗ",
                   description="Временный проект самотеста", nodes=nodes, boards=boards)


def run_report_text(cause: str, method: str, card: str, verdict: str) -> str:
    insights = [
        {"method_id": method, "card_id": card,
         "question": f"Выполняется ли правило решения для {cause}?",
         "answer": "2+2=4, порог пройден",
         "narrative": "Да: проверка сошлась точно.",
         "certainty": "definite", "importance": 4},
        {"method_id": method, "card_id": card,
         "question": "Есть ли оговорки воспроизводимости?",
         "answer": "прогон синтетический",
         "narrative": "Прогон синтетический, оговорок нет.",
         "certainty": "tentative", "importance": 2},
    ]
    return f"""# Отчёт о прогоне: самотест

## 0. Привязка

| Поле | Значение |
|------|----------|
| Гипотеза (cause) | `{cause}` — тестовая |
| Метод / карточка | `{method}` / `{card}` |
| Спека гипотезы | да |
| Дата прогона | 2026-06-11 |
| Агент-исполнитель | самотест |
| Статус прогона | завершён успешно |

## 1. Что запущено (воспроизводимость)

- Команда: `python -c 'print(2+2)'`

## 2. Основная метрика и результаты

| tag | осн. метрика |
|-----|--------------|
| selftest | 4 |

Сводка одной фразой: вычисление дало 4.

## 3. Проверка правила решения

- Правило (из спеки): supported если 2+2=4
- Факт: 2+2 = 4
- → правило даёт: **{verdict}**

## 4. Угрозы и оговорки (что этот прогон НЕ доказывает)

- Прогон синтетический, реальную систему не проверяет.

## 5. Заявка в базу знаний

### 5.1 Предлагаемый вердикт cause-узла

- `{cause}` → **{verdict}**
- обоснование: правило решения из §3 выполнено.

### 5.2 Предлагаемые инсайты (≤3 на метод, формат research.json)

```json
{json.dumps(insights, ensure_ascii=False, indent=2)}
```

### 5.3 Рекомендация по форме интеграции

- Рекомендация: принять как есть.
- Почему: синтетический порог пройден точно.
"""


def main() -> int:
    mount = get_mount(PID)
    if mount and mount.repo_root.exists():
        shutil.rmtree(mount.repo_root)
        rescan_projects()
    stub_dir = Path(tempfile.mkdtemp(prefix="koi-claude-stub-"))
    try:
        print("== 1. Создание проекта → инициализация БЗ")
        create_project("kb selftest")
        project = make_project()
        save_project(project)
        pdir = project_dir()
        check("KNOWLEDGE.md создан", (pdir / "KNOWLEDGE.md").is_file())
        check("knowledge/hypotheses.md создан",
              (pdir / "knowledge" / "hypotheses.md").is_file())
        log0 = (pdir / "KNOWLEDGE_LOG.md").read_text(encoding="utf-8")
        check("журнал инициализирован", "Инициализация журнала" in log0)

        print("== 2. Ingest отчёта (карточка card-arith)")
        project = load_project(PID)
        board = next(b for b in project.boards if b.id == "board-m-test")
        card = next(c for c in board.cards if c.id == "card-arith")
        run_path = expected_run_report_path(project, board.id, card.id, card.title)
        run_path.write_text(
            run_report_text("c-test", "m-test", "card-arith", "supported"),
            encoding="utf-8")
        summary = ingest_report(PID, run_path)
        check("вердикт open→supported",
              summary["verdict"] == {"node": "c-test", "old": "open", "new": "supported"})
        check("2 инсайта добавлены", summary["insights"]["added"] ==
              ["rq-card-arith-1", "rq-card-arith-2"])
        check("карточка → done", summary["card_moved"]["new"] == "done")

        project = load_project(PID)
        cause = next(n for n in project.nodes if n.id == "c-test")
        method = next(n for n in project.nodes if n.id == "m-test")
        check("verdict сохранён в project.md", cause.verdict == Verdict.SUPPORTED)
        check("инсайты сохранены в research.json",
              [q.id for q in method.research_questions] ==
              ["rq-card-arith-1", "rq-card-arith-2"])
        kmd = (pdir / "KNOWLEDGE.md").read_text(encoding="utf-8")
        check("KNOWLEDGE.md показывает ✔", "✔" in kmd and "инсайтов: 2" in kmd)
        log1 = (pdir / "KNOWLEDGE_LOG.md").read_text(encoding="utf-8")
        check("журнал: смена вердикта", "✔ подтверждена" in log1)
        check("журнал: новые инсайты", log1.count("Новый инсайт") >= 2)

        print("== 3. Повторный ingest — идемпотентность")
        sections_before = log1.count("\n## ")
        summary2 = ingest_report(PID, run_path)
        log2 = (pdir / "KNOWLEDGE_LOG.md").read_text(encoding="utf-8")
        check("повторный ingest без новых записей журнала",
              log2.count("\n## ") == sections_before)
        check("инсайты не задублированы",
              summary2["insights"]["added"] == ["rq-card-arith-1", "rq-card-arith-2"])

        print("== 4. Стаб Claude Code CLI → koi_check_hypothesis end-to-end")
        canned = stub_dir / "canned.run.md"
        canned.write_text(
            run_report_text("c-test2", "m-test2", "card-stub", "supported"),
            encoding="utf-8")
        stub = stub_dir / "claude"
        stub.write_text(
            "#!/usr/bin/env bash\n"
            "# Стаб Claude Code CLI: берёт путь отчёта из промпта и кладёт туда canned-отчёт\n"
            "prompt=$(cat)\n"
            "path=$(printf '%s' \"$prompt\" | grep -oP 'Файл отчёта: `\\K[^`]+' | head -1)\n"
            "[ -n \"$path\" ] || { echo 'no path in prompt' >&2; exit 1; }\n"
            f"cp '{canned}' \"$path\"\n"
            "echo \"stub: отчёт записан в $path\"\n",
            encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, KOI_CLAUDE_BIN=str(stub),
                   KOI_AGENT_BACKEND="claude", PYTHONPATH=str(ROOT))
        proc = subprocess.run(
            [sys.executable, "scripts/koi_check_hypothesis.py", PID, "card-stub"],
            capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=120)
        check("раннер завершился успешно", proc.returncode == 0,
              (proc.stderr or "").strip()[-200:] if proc.returncode else "")
        project = load_project(PID)
        cause2 = next(n for n in project.nodes if n.id == "c-test2")
        method2 = next(n for n in project.nodes if n.id == "m-test2")
        board2 = next(b for b in project.boards if b.id == "board-m-test2")
        card2 = next(c for c in board2.cards if c.id == "card-stub")
        check("стаб-цепочка: вердикт supported", cause2.verdict == Verdict.SUPPORTED)
        check("стаб-цепочка: инсайты на методе",
              len(method2.research_questions) == 2)
        check("стаб-цепочка: карточка done", card2.column_id == "done")
        log3 = (pdir / "KNOWLEDGE_LOG.md").read_text(encoding="utf-8")
        check("журнал пополнился второй гипотезой",
              "Вторая гипотеза" in log3 or "c-test2" in log3
              or log3.count("✔ подтверждена") >= 2)

        print("== 5. Отказоустойчивость: отчёт без §5.2-json отклоняется")
        bad = run_path.with_name("bad.run.md")
        bad.write_text(
            run_report_text("c-test", "m-test", "card-arith", "supported")
            .replace("```json", "```text"),
            encoding="utf-8")
        try:
            ingest_report(PID, bad)
            check("невалидный отчёт отклонён", False)
        except Exception as e:
            check("невалидный отчёт отклонён", "json" in str(e).lower(), str(e)[:80])

        failed = [c for c in CHECKS if not c[1]]
        print(f"\nИтог: {len(CHECKS) - len(failed)}/{len(CHECKS)} PASS"
              + (f", FAIL: {[c[0] for c in failed]}" if failed else ""))
        return 1 if failed else 0
    finally:
        mount = get_mount(PID)
        if mount and mount.repo_root.exists():
            shutil.rmtree(mount.repo_root)
            rescan_projects()
        shutil.rmtree(stub_dir, ignore_errors=True)
        print("Очистка: projects/kb-selftest/ и стаб удалены.")


if __name__ == "__main__":
    raise SystemExit(main())
