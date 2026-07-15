"""Pure parsing and validation of experiment ``.run.md`` reports."""

from __future__ import annotations

import json
import re

from koi.core.models import MethodResearchQuestion, ResearchQuestionCertainty
from koi.projects.report_ingest.models import ReportClaim, ReportIngestError


_BACKTICK = re.compile(r"`([^`]+)`")
_VERDICT_LINE = re.compile(
    r"`(?P<node>[\w./-]+)`\s*(?:→|->|=>)\s*.*?\*\*(?P<verdict>open|supported|refuted)\*\*",
    re.IGNORECASE,
)
_JSON_FENCE = re.compile(r"```json\s*\n(?P<body>.*?)\n```", re.DOTALL)


def _section(text: str, number: int) -> str:
    lines = text.splitlines()
    output: list[str] = []
    inside = False
    heading = re.compile(rf"^##\s*{number}\.")
    for line in lines:
        if inside and re.match(r"^##\s", line) and not line.startswith("###"):
            break
        if heading.match(line):
            inside = True
            continue
        if inside:
            output.append(line)
    return "\n".join(output)


def parse_run_report(text: str) -> ReportClaim:
    claim = ReportClaim()
    anchor = _section(text, 0)
    for line in anchor.splitlines():
        if "|" not in line:
            continue
        identifiers = _BACKTICK.findall(line)
        lowered = line.lower()
        if "гипотеза" in lowered and identifiers:
            claim.cause_id = identifiers[0]
        elif ("метод" in lowered or "карточка" in lowered) and identifiers:
            claim.method_id = identifiers[0]
            if len(identifiers) > 1:
                claim.card_id = identifiers[1]
            else:
                tail = line.rsplit("/", 1)[-1].strip(" |")
                tail = tail.strip("`").strip()
                if tail and " " not in tail:
                    claim.card_id = tail

    knowledge_section = _section(text, 5)
    if not knowledge_section.strip():
        raise ReportIngestError("В отчёте нет секции «## 5. Заявка в базу знаний»")

    verdict_match = _VERDICT_LINE.search(knowledge_section)
    if verdict_match:
        claim.verdict = verdict_match.group("verdict").lower()
        claim.cause_id = verdict_match.group("node") or claim.cause_id
    else:
        claim.warnings.append(
            "В §5.1 не найден вердикт вида «`c-…` → **supported|refuted|open**»"
        )

    json_match = _JSON_FENCE.search(knowledge_section)
    if not json_match:
        raise ReportIngestError(
            "В §5.2 нет fenced ```json блока с инсайтами (формат research.json) — "
            "автоинтеграция без него невозможна"
        )
    try:
        data = json.loads(json_match.group("body"))
    except json.JSONDecodeError as error:
        raise ReportIngestError(f"§5.2: невалидный JSON: {error}") from error
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ReportIngestError("§5.2: ожидается JSON-массив объектов-инсайтов")
    claim.insights = data

    for item in data:
        claim.method_id = claim.method_id or item.get("method_id")
        claim.card_id = claim.card_id or item.get("card_id")
    if not claim.method_id or not claim.card_id:
        raise ReportIngestError(
            "Не удалось определить method_id/card_id (ни в §0 «Привязка», ни в §5.2)"
        )
    return claim


def build_questions(claim: ReportClaim) -> list[MethodResearchQuestion]:
    questions: list[MethodResearchQuestion] = []
    for index, item in enumerate(claim.insights, start=1):
        question = str(item.get("question", "")).strip()
        if not question:
            raise ReportIngestError(f"§5.2: у инсайта №{index} пустой question")
        certainty = str(item.get("certainty", "tentative")).strip().lower()
        if certainty not in ("definite", "tentative"):
            claim.warnings.append(
                f"§5.2: инсайт №{index}: certainty «{certainty}» → tentative"
            )
            certainty = "tentative"
        try:
            importance = max(1, min(5, int(item.get("importance", 3))))
        except (TypeError, ValueError):
            importance = 3
        questions.append(
            MethodResearchQuestion(
                id=str(item.get("id") or f"rq-{claim.card_id}-{index}"),
                question=question,
                answer=str(item.get("answer", "")).strip(),
                narrative=str(item.get("narrative", "")).strip(),
                certainty=ResearchQuestionCertainty(certainty),
                importance=importance,
                card_id=claim.card_id,
            )
        )
    return questions


_build_questions = build_questions
