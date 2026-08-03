"""Filesystem workflow for generated project knowledge artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from koi.adapters.paths import (
    knowledge_dir as project_knowledge_dir,
    knowledge_log_path as project_knowledge_log_path,
    knowledge_path as project_knowledge_path,
    reports_dir,
)
from koi.core.models import Project, Verdict
from koi.knowledge.model import (
    KnowledgeDocument,
    VERDICT_MARK,
    causes,
    methods_under,
    shorten,
)
from koi.knowledge.rendering import render_hypotheses, render_project_index
from koi.knowledge.summary import build_summary


GENERATED_DOC = "hypotheses.md"
STATE_FILE = ".state.json"


def knowledge_path(project_id: str) -> Path:
    return project_knowledge_path(project_id)


def knowledge_dir(project_id: str) -> Path:
    return project_knowledge_dir(project_id)


def knowledge_log_path(project_id: str) -> Path:
    return project_knowledge_log_path(project_id)


def _report_index(project_id: str) -> dict:
    path = reports_dir(project_id) / "index.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _doc_meta(path: Path) -> tuple[str, str]:
    title, summary = path.stem, ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return title, summary
    heading_index = 0
    for heading_index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            break
    for line in lines[heading_index + 1 :]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if summary:
                break
            continue
        summary += (" " if summary else "") + stripped.lstrip("> ").strip()
    return title, shorten(summary)


def _list_doc_paths(project_id: str) -> list[Path]:
    directory = knowledge_dir(project_id)
    if not directory.is_dir():
        return []
    curated = sorted(
        path for path in directory.glob("*.md") if path.name != GENERATED_DOC
    )
    generated = directory / GENERATED_DOC
    return curated + ([generated] if generated.exists() else [])


def _documents(project_id: str) -> list[KnowledgeDocument]:
    return [
        KnowledgeDocument(name=path.name, title=title, summary=summary)
        for path in _list_doc_paths(project_id)
        for title, summary in [_doc_meta(path)]
    ]


def render_hypotheses_doc(
    project: Project, report_index: dict | None = None
) -> str:
    resolved = report_index if report_index is not None else _report_index(project.id)
    return render_hypotheses(project, resolved)


def render_project_knowledge(
    project: Project, report_index: dict | None = None
) -> str:
    resolved = report_index if report_index is not None else _report_index(project.id)
    return render_project_index(project, resolved, _documents(project.id))


def _recent_log_sections(project_id: str, limit: int = 10) -> list[dict]:
    path = knowledge_log_path(project_id)
    if not path.exists():
        return []
    sections: list[dict] = []
    current: dict | None = None
    total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if total >= limit:
                break
            current = {"stamp": line[3:].strip(), "entries": []}
            sections.append(current)
        elif current is not None and line.startswith("- "):
            current["entries"].append(line[2:].strip())
            total += 1
    return (
        [section for section in sections if section["entries"] or section is sections[0]]
        if sections
        else []
    )


def _pages_for_docs(project_id: str) -> list:
    try:
        from koi.adapters.pages import list_pages_for_docs

        return list_pages_for_docs(project_id)
    except Exception:
        return []


def knowledge_summary(project: Project) -> dict:
    return build_summary(
        project,
        report_index=_report_index(project.id),
        documents=_documents(project.id),
        recent_log=_recent_log_sections(project.id),
        pages=_pages_for_docs(project.id),
    )


def _question_fingerprint(question) -> str:
    raw = "\x00".join(
        [
            question.question,
            question.answer,
            question.narrative,
            question.certainty.value,
            str(question.importance),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _snapshot(project: Project, docs: list[Path]) -> dict:
    verdicts, questions = {}, {}
    for cause in causes(project):
        verdicts[cause.id] = {"verdict": cause.verdict.value, "title": cause.title}
        for method in methods_under(project.nodes, cause.id):
            for question in method.research_questions:
                questions[question.id] = {
                    "question": question.question,
                    "card_id": question.card_id or "",
                    "method_title": method.title,
                    "fp": _question_fingerprint(question),
                }
    return {
        "version": 1,
        "verdicts": verdicts,
        "questions": questions,
        "docs": {
            doc.name: _doc_meta(doc)[0]
            for doc in docs
            if doc.name != GENERATED_DOC
        },
    }


def _diff_entries(old: dict, new: dict, project: Project) -> list[str]:
    entries: list[str] = []
    old_verdicts, new_verdicts = old.get("verdicts", {}), new["verdicts"]
    for cause_id, current in new_verdicts.items():
        previous = old_verdicts.get(cause_id)
        if previous is None:
            if current["verdict"] != Verdict.OPEN.value:
                mark = VERDICT_MARK[Verdict(current["verdict"])]
                entries.append(
                    f"- Вердикт «{current['title']}» (`{cause_id}`): {mark}"
                )
        elif previous["verdict"] != current["verdict"]:
            old_mark = VERDICT_MARK[Verdict(previous["verdict"])]
            new_mark = VERDICT_MARK[Verdict(current["verdict"])]
            entries.append(
                f"- Вердикт «{current['title']}» (`{cause_id}`): "
                f"{old_mark} → {new_mark}"
            )

    old_questions, new_questions = old.get("questions", {}), new["questions"]
    for question_id, current in new_questions.items():
        previous = old_questions.get(question_id)
        source = f"метод «{shorten(current['method_title'], 60)}»"
        if current["card_id"]:
            source += f", карточка `{current['card_id']}`"
        if previous is None:
            entries.append(
                f"- Новый инсайт ({source}): «{shorten(current['question'], 120)}»"
            )
        elif previous.get("fp") != current["fp"]:
            entries.append(
                f"- Обновлён инсайт ({source}): «{shorten(current['question'], 120)}»"
            )
    for question_id, previous in old_questions.items():
        if question_id not in new_questions:
            entries.append(
                f"- Удалён инсайт: «{shorten(previous.get('question', question_id), 120)}»"
            )

    old_docs, new_docs = old.get("docs", {}), new["docs"]
    for name, title in new_docs.items():
        if name not in old_docs:
            entries.append(f"- Новый документ: [{title}](knowledge/{name})")
    for name, title in old_docs.items():
        if name not in new_docs:
            entries.append(f"- Удалён документ: {title} (`knowledge/{name}`)")
    return entries


def _append_log(project: Project, entries: list[str], initial: bool) -> None:
    path = knowledge_log_path(project.id)
    header = (
        f"# Журнал базы знаний: {project.title}\n\n"
        "Записи добавляются автоматически при сохранении проекта: смена вердикта,\n"
        "новый/обновлённый инсайт в research.json, новый документ в `knowledge/`.\n"
        "Свежие записи сверху.\n"
    )
    old_body = ""
    if path.exists():
        text = path.read_text(encoding="utf-8")
        index = text.find("\n## ")
        if index != -1:
            old_body = text[index:]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    section = [f"\n## {stamp}", ""]
    if initial:
        section.append("_Инициализация журнала — зафиксировано текущее состояние БЗ._")
    section += entries + [""]
    path.write_text(header + "\n".join(section) + old_body, encoding="utf-8")


def write_project_knowledge(project: Project) -> Path:
    directory = knowledge_dir(project.id)
    directory.mkdir(parents=True, exist_ok=True)
    report_index = _report_index(project.id)
    (directory / GENERATED_DOC).write_text(
        render_hypotheses_doc(project, report_index), encoding="utf-8"
    )

    state_path = directory / STATE_FILE
    old_state, initial = {}, True
    if state_path.exists():
        try:
            old_state = json.loads(state_path.read_text(encoding="utf-8"))
            initial = False
        except (json.JSONDecodeError, OSError):
            pass
    new_state = _snapshot(project, _list_doc_paths(project.id))
    entries = _diff_entries(old_state, new_state, project)
    if entries or initial:
        _append_log(project, entries, initial)
    state_path.write_text(
        json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    path = knowledge_path(project.id)
    path.write_text(render_project_knowledge(project, report_index), encoding="utf-8")
    return path
