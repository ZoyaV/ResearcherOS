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
        if "hypothesis" in lowered and identifiers:
            claim.cause_id = identifiers[0]
        elif ("method" in lowered or "card" in lowered) and identifiers:
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
        raise ReportIngestError(
            'The report is missing the "## 5. Knowledge base submission" section'
        )

    verdict_match = _VERDICT_LINE.search(knowledge_section)
    if verdict_match:
        claim.verdict = verdict_match.group("verdict").lower()
        claim.cause_id = verdict_match.group("node") or claim.cause_id
    else:
        claim.warnings.append(
            "Section 5.1 has no verdict in the form "
            '"`c-…` → **supported|refuted|open**"'
        )

    json_match = _JSON_FENCE.search(knowledge_section)
    if not json_match:
        raise ReportIngestError(
            "Section 5.2 has no fenced ```json block with insights "
            "(research.json format); automatic integration requires it"
        )
    try:
        data = json.loads(json_match.group("body"))
    except json.JSONDecodeError as error:
        raise ReportIngestError(f"Section 5.2: invalid JSON: {error}") from error
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ReportIngestError(
            "Section 5.2 must contain a JSON array of insight objects"
        )
    claim.insights = data

    for item in data:
        claim.method_id = claim.method_id or item.get("method_id")
        claim.card_id = claim.card_id or item.get("card_id")
    if not claim.method_id or not claim.card_id:
        raise ReportIngestError(
            "Could not determine method_id/card_id from either "
            'Section 0 "References" or Section 5.2'
        )
    return claim


def build_questions(claim: ReportClaim) -> list[MethodResearchQuestion]:
    questions: list[MethodResearchQuestion] = []
    for index, item in enumerate(claim.insights, start=1):
        question = str(item.get("question", "")).strip()
        if not question:
            raise ReportIngestError(
                f"Section 5.2: insight #{index} has an empty question"
            )
        certainty = str(item.get("certainty", "tentative")).strip().lower()
        if certainty not in ("definite", "tentative"):
            claim.warnings.append(
                f'Section 5.2: insight #{index}: certainty "{certainty}" → tentative'
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
