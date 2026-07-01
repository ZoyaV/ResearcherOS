"""Авто-интеграция рабочего отчёта эксперимента в проект и базу знаний.

Вход — `.run.md`, заполненный по `agent/templates/experiment-report.md`.
Из него извлекаются: привязка (§0: cause / method / карточка), предлагаемый
вердикт (§5.1) и инсайты в формате research.json (§5.2, fenced ```json блок).

Применение (`ingest_report`): вердикт ставится на cause-узел, инсайты
заменяют прежние инсайты этой карточки на методе (повторный ingest того же
отчёта идемпотентен), карточка переезжает в done, `reports/index.json`
получает запись. Один вызов `save_project` в конце триггерит штатный хук
базы знаний — KNOWLEDGE.md / knowledge/hypotheses.md / KNOWLEDGE_LOG.md
пересобираются автоматически.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from koi.adapters.card_reports import ensure_card_report, load_index, reports_dir
from koi.core.models import (
    MAX_METHOD_RESEARCH_QUESTIONS,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
    ResearchQuestionCertainty,
    Verdict,
)
from koi.adapters.repository import load_project, save_project

RUN_SUFFIX = ".run.md"

_BACKTICK = re.compile(r"`([^`]+)`")
_VERDICT_LINE = re.compile(
    r"`(?P<node>[\w./-]+)`\s*(?:→|->|=>)\s*.*?\*\*(?P<verdict>open|supported|refuted)\*\*",
    re.IGNORECASE,
)
_JSON_FENCE = re.compile(r"```json\s*\n(?P<body>.*?)\n```", re.DOTALL)


class ReportIngestError(ValueError):
    """Отчёт не пригоден для автоинтеграции; текст ошибки — что чинить."""


@dataclass
class ReportClaim:
    """Машиночитаемая «Заявка в базу знаний» из .run.md."""

    cause_id: Optional[str] = None
    verdict: Optional[str] = None
    method_id: Optional[str] = None
    card_id: Optional[str] = None
    insights: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _section(text: str, number: int) -> str:
    """Тело секции `## <number>.` до следующего `## `."""
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    head = re.compile(rf"^##\s*{number}\.")
    for line in lines:
        if inside and re.match(r"^##\s", line) and not line.startswith("###"):
            break
        if head.match(line):
            inside = True
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


def parse_run_report(text: str) -> ReportClaim:
    claim = ReportClaim()

    # §0 «Привязка» — таблица | Поле | Значение |
    anchor = _section(text, 0)
    for line in anchor.splitlines():
        if "|" not in line:
            continue
        ids = _BACKTICK.findall(line)
        low = line.lower()
        if "гипотеза" in low and ids:
            claim.cause_id = ids[0]
        elif ("метод" in low or "карточка" in low) and ids:
            claim.method_id = ids[0]
            if len(ids) > 1:
                claim.card_id = ids[1]
            else:
                # карточка могла быть записана без бэктиков: `m-…` / card-id
                tail = line.rsplit("/", 1)[-1].strip(" |")
                tail = tail.strip("`").strip()
                if tail and " " not in tail:
                    claim.card_id = tail

    # §5 «Заявка в базу знаний»
    five = _section(text, 5)
    if not five.strip():
        raise ReportIngestError("В отчёте нет секции «## 5. Заявка в базу знаний»")

    m = _VERDICT_LINE.search(five)
    if m:
        claim.verdict = m.group("verdict").lower()
        # §5.1 авторитетнее §0, если там назван узел
        claim.cause_id = m.group("node") or claim.cause_id
    else:
        claim.warnings.append(
            "В §5.1 не найден вердикт вида «`c-…` → **supported|refuted|open**»"
        )

    j = _JSON_FENCE.search(five)
    if not j:
        raise ReportIngestError(
            "В §5.2 нет fenced ```json блока с инсайтами (формат research.json) — "
            "автоинтеграция без него невозможна"
        )
    try:
        data = json.loads(j.group("body"))
    except json.JSONDecodeError as e:
        raise ReportIngestError(f"§5.2: невалидный JSON: {e}") from e
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
        raise ReportIngestError("§5.2: ожидается JSON-массив объектов-инсайтов")
    if len(data) > MAX_METHOD_RESEARCH_QUESTIONS:
        raise ReportIngestError(
            f"§5.2: инсайтов {len(data)} — больше лимита "
            f"{MAX_METHOD_RESEARCH_QUESTIONS} на метод; сократите заявку"
        )
    claim.insights = data

    # method/card из инсайтов — запасной источник привязки
    for item in data:
        claim.method_id = claim.method_id or item.get("method_id")
        claim.card_id = claim.card_id or item.get("card_id")

    if not claim.method_id or not claim.card_id:
        raise ReportIngestError(
            "Не удалось определить method_id/card_id (ни в §0 «Привязка», ни в §5.2)"
        )
    return claim


def _find_node(project: Project, node_id: str) -> Optional[Node]:
    return next((n for n in project.nodes if n.id == node_id), None)


def _build_questions(claim: ReportClaim) -> list[MethodResearchQuestion]:
    out: list[MethodResearchQuestion] = []
    for i, item in enumerate(claim.insights, start=1):
        question = str(item.get("question", "")).strip()
        if not question:
            raise ReportIngestError(f"§5.2: у инсайта №{i} пустой question")
        certainty = str(item.get("certainty", "tentative")).strip().lower()
        if certainty not in ("definite", "tentative"):
            claim.warnings.append(
                f"§5.2: инсайт №{i}: certainty «{certainty}» → tentative"
            )
            certainty = "tentative"
        try:
            importance = max(1, min(5, int(item.get("importance", 3))))
        except (TypeError, ValueError):
            importance = 3
        out.append(
            MethodResearchQuestion(
                # детерминированный id — повторный ingest не плодит дубликатов
                id=str(item.get("id") or f"rq-{claim.card_id}-{i}"),
                question=question,
                answer=str(item.get("answer", "")).strip(),
                narrative=str(item.get("narrative", "")).strip(),
                certainty=ResearchQuestionCertainty(certainty),
                importance=importance,
                card_id=claim.card_id,
            )
        )
    return out


def ingest_report(
    project_id: str, report_path: str | Path, *, dry_run: bool = False
) -> dict:
    """Применить заявку из .run.md к проекту. Возвращает сводку изменений."""
    path = Path(report_path)
    if not path.is_file():
        raise ReportIngestError(f"Файл отчёта не найден: {path}")
    claim = parse_run_report(path.read_text(encoding="utf-8"))

    project = load_project(project_id)
    if project is None:
        raise ReportIngestError(f"Проект не найден: {project_id}")

    method = _find_node(project, claim.method_id)
    if method is None or method.node_type != NodeType.METHOD:
        raise ReportIngestError(f"Узел-метод не найден: {claim.method_id}")
    board = next(
        (b for b in project.boards if b.owner_node_id == method.id), None
    )
    card = (
        next((c for c in board.cards if c.id == claim.card_id), None)
        if board
        else None
    )
    if card is None:
        raise ReportIngestError(
            f"Карточка {claim.card_id} не найдена на доске метода {method.id}"
        )

    summary: dict = {
        "project": project_id,
        "report": str(path),
        "cause_id": claim.cause_id,
        "method_id": method.id,
        "card_id": card.id,
        "warnings": list(claim.warnings),
        "dry_run": dry_run,
    }

    # 1. Вердикт cause-узла
    if claim.verdict and claim.cause_id:
        cause = _find_node(project, claim.cause_id)
        if cause is None:
            claim.warnings.append(f"Узел гипотезы не найден: {claim.cause_id}")
            summary["verdict"] = None
        else:
            if cause.node_type != NodeType.CAUSE:
                claim.warnings.append(
                    f"{claim.cause_id} имеет тип {cause.node_type}, не cause"
                )
            summary["verdict"] = {
                "node": cause.id,
                "old": cause.verdict.value,
                "new": claim.verdict,
            }
            if not dry_run:
                cause.verdict = Verdict(claim.verdict)
    else:
        summary["verdict"] = None

    # 2. Инсайты: заменяем прежние инсайты ЭТОЙ карточки, чужие не трогаем
    new_qs = _build_questions(claim)
    kept = [q for q in method.research_questions if q.card_id != card.id]
    dropped: list[str] = []
    overflow = len(kept) + len(new_qs) - MAX_METHOD_RESEARCH_QUESTIONS
    if overflow > 0:
        kept.sort(key=lambda q: q.importance, reverse=True)
        dropped = [q.id for q in kept[len(kept) - overflow :]]
        kept = kept[: len(kept) - overflow]
    summary["insights"] = {
        "added": [q.id for q in new_qs],
        "kept": [q.id for q in kept],
        "dropped": dropped,
    }
    if not dry_run:
        method.research_questions = kept + new_qs

    # 3. Карточка → done
    summary["card_moved"] = {"old": card.column_id, "new": "done"}
    if not dry_run:
        card.column_id = "done"

    # 4. reports/index.json (+ пустой публичный .md, если его ещё нет)
    if not dry_run:
        ensure_card_report(project, board.id, card.id, card.title)
    summary["public_report"] = load_index(project_id).get(card.id)

    # 5. Один save — штатный хук пересоберёт KNOWLEDGE.md и журнал
    if not dry_run:
        save_project(project)
        summary["knowledge_updated"] = True
    summary["warnings"] = list(claim.warnings)
    return summary


def expected_run_report_path(
    project: Project, board_id: str, card_id: str, card_title: str
) -> Path:
    """Куда эксперимент-агент должен положить .run.md для карточки."""
    public = ensure_card_report(project, board_id, card_id, card_title)
    return public.with_name(public.name[: -len(".md")] + RUN_SUFFIX)
