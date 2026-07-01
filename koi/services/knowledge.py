"""Per-project knowledge base, generated from the project's own KOI data.

Структура БЗ у каждого проекта (всё лежит в `projects/<id>/`):

    KNOWLEDGE.md       компактное оглавление: статистика, сводка по каждому
                       документу со ссылкой на него, статус гипотез. Не раздувается —
                       полные тексты живут в knowledge/.
    KNOWLEDGE_LOG.md   журнал пополнений: что и когда записалось в БЗ
                       (смена вердикта, новый/обновлённый инсайт, новый документ).
    knowledge/         полные документы знаний (.md):
        hypotheses.md  АВТОГЕН: гипотезы, вердикты, все инсайты со ссылками на отчёты;
        <NN-имя>.md    курируемые: обзор проекта, установка, запуск, скрипты, грабли…
        .state.json    служебный снапшот для автодиффа журнала.

Конвенция документа: первая строка `# Заголовок`, первый абзац после него —
краткая сводка (она попадает в оглавление KNOWLEDGE.md).

Автоматическая интеграция новых знаний:
  1) агент/пользователь меняет verdict в project.md или добавляет инсайт в
     research.json → `save_project` пересобирает hypotheses.md, KNOWLEDGE.md
     и дописывает запись в KNOWLEDGE_LOG.md;
  2) новый .md, положенный в knowledge/, автоматически появляется в оглавлении
     и в журнале при следующем сохранении проекта (или `python agent/bin/build_kb.py`).
Руками KNOWLEDGE.md, knowledge/hypotheses.md и KNOWLEDGE_LOG.md не правят.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from koi.core.models import NodeType, Project, Verdict

from koi.adapters.paths import (
    knowledge_dir as project_knowledge_dir,
    knowledge_log_path as project_knowledge_log_path,
    knowledge_path as project_knowledge_path,
    reports_dir,
)

GENERATED_DOC = "hypotheses.md"
STATE_FILE = ".state.json"

VERDICT_MARK = {
    Verdict.SUPPORTED: "✔ подтверждена",
    Verdict.REFUTED: "✗ опровергнута",
    Verdict.OPEN: "… открыта",
}


def knowledge_path(project_id: str) -> Path:
    return project_knowledge_path(project_id)


def knowledge_dir(project_id: str) -> Path:
    return project_knowledge_dir(project_id)


def knowledge_log_path(project_id: str) -> Path:
    return project_knowledge_log_path(project_id)


def _report_index(project_id: str) -> dict:
    p = reports_dir(project_id) / "index.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _children(nodes, parent_id):
    return [n for n in nodes if n.parent_id == parent_id]


def _methods_under(nodes, cause_id):
    """method-узлы в поддереве гипотезы: cause → cause_evidence/remediation → method."""
    out = []
    for mid in _children(nodes, cause_id):
        for m in _children(nodes, mid.id):
            if m.node_type == NodeType.METHOD:
                out.append(m)
    return out


def _short(text: str, limit: int = 180) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _doc_meta(path: Path) -> tuple[str, str]:
    """(заголовок, сводка) документа: H1 + первый абзац после него."""
    title, summary = path.stem, ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return title, summary
    i = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            break
    for line in lines[i + 1 :]:
        s = line.strip()
        if not s or s.startswith("#"):
            if summary:
                break
            continue
        summary += (" " if summary else "") + s.lstrip("> ").strip()
    return title, _short(summary)


def _list_docs(project_id: str) -> list[Path]:
    kdir = knowledge_dir(project_id)
    if not kdir.is_dir():
        return []
    return sorted(p for p in kdir.glob("*.md") if p.name != GENERATED_DOC) + (
        [kdir / GENERATED_DOC] if (kdir / GENERATED_DOC).exists() else []
    )


def _causes(project: Project):
    return sorted(
        (n for n in project.nodes if n.node_type == NodeType.CAUSE),
        key=lambda n: n.title,
    )


def _stats(project: Project):
    causes = _causes(project)
    supported = sum(1 for c in causes if c.verdict == Verdict.SUPPORTED)
    refuted = sum(1 for c in causes if c.verdict == Verdict.REFUTED)
    insights = sum(
        len(m.research_questions)
        for c in causes
        for m in _methods_under(project.nodes, c.id)
    )
    return causes, supported, refuted, insights


def render_hypotheses_doc(project: Project, report_index: dict | None = None) -> str:
    """knowledge/hypotheses.md — полная картина гипотез: вердикты + все инсайты."""
    report_index = report_index if report_index is not None else _report_index(project.id)
    nodes = project.nodes
    causes, supported, refuted, insights = _stats(project)

    lines = [
        "# Гипотезы и результаты",
        "",
        f"Автовыжимка по {len(causes)} гипотезам (подтверждено: {supported}, "
        f"опровергнуто: {refuted}, открыто: {len(causes) - supported - refuted}; "
        f"инсайтов: {insights}). Источник — project.md и research.json, "
        "пересобирается при каждом сохранении проекта; не править руками.",
        "",
    ]
    for cause in causes:
        mark = VERDICT_MARK.get(cause.verdict, cause.verdict.value)
        lines += [f"## {cause.title}", "", f"Вердикт: {mark}  ·  узел `{cause.id}`", ""]
        if cause.description:
            lines += [cause.description, ""]
        had = False
        for method in _methods_under(nodes, cause.id):
            for q in method.research_questions:
                had = True
                src = f"метод `{method.id}`"
                if q.card_id:
                    src += f", карточка `{q.card_id}`"
                    rep = report_index.get(q.card_id)
                    if rep:
                        src += f" → [отчёт](../reports/{rep})"
                narrative = q.narrative or q.answer or "—"
                lines += [
                    f"- {q.question}",
                    f"  - {narrative}  _(уверенность: {q.certainty.value}, "
                    f"важность: {q.importance}/5; {src})_",
                ]
        if not had:
            lines.append("- _инсайтов пока нет (эксперимент не закрыт)._")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_project_knowledge(project: Project, report_index: dict | None = None) -> str:
    """KNOWLEDGE.md — компактное оглавление БЗ проекта (сводки + ссылки)."""
    report_index = report_index if report_index is not None else _report_index(project.id)
    causes, supported, refuted, insights = _stats(project)
    problem = next((n for n in project.nodes if n.node_type == NodeType.PROBLEM), None)
    docs = _list_docs(project.id)

    lines = [
        f"# База знаний: {project.title}",
        "",
        "Оглавление базы знаний проекта: краткие сводки и ссылки, полные документы — ",
        "в [`knowledge/`](knowledge/), журнал пополнений — в "
        "[KNOWLEDGE_LOG.md](KNOWLEDGE_LOG.md). Генерируется автоматически при каждом ",
        "сохранении проекта (`koi/knowledge.py`) — не править руками.",
        "",
        f"Проект: `{project.id}` · гипотез: {len(causes)} "
        f"(✔ {supported} · ✗ {refuted} · … {len(causes) - supported - refuted}) "
        f"· инсайтов: {insights} · документов: {len(docs)}",
        "",
    ]
    if problem:
        lines += ["## Проблема", "", f"**{problem.title}.** {_short(problem.description, 400)}", ""]

    lines += ["## Документы", ""]
    if not docs:
        lines += ["_Документов пока нет — положите .md в `knowledge/` (см. конвенцию в agent/process.md)._", ""]
    for doc in docs:
        title, summary = _doc_meta(doc)
        entry = f"- [{title}](knowledge/{doc.name})"
        if summary:
            entry += f" — {summary}"
        lines.append(entry)
    lines.append("")

    lines += ["## Гипотезы — статус", ""]
    if not causes:
        lines += ["_Гипотез пока нет._", ""]
    for cause in causes:
        mark = VERDICT_MARK.get(cause.verdict, cause.verdict.value)
        qs = [
            q
            for method in _methods_under(project.nodes, cause.id)
            for q in method.research_questions
        ]
        entry = f"- {mark} — [{cause.title}](knowledge/{GENERATED_DOC})"
        if qs:
            entry += f" · инсайтов: {len(qs)}"
        rep = next(
            (report_index[q.card_id] for q in qs if q.card_id and q.card_id in report_index),
            None,
        )
        if rep:
            entry += f" · [отчёт](reports/{rep})"
        lines.append(entry)
        if qs:
            top = max(qs, key=lambda q: q.importance)
            text = top.narrative or top.answer
            if text:
                lines.append(f"  - итог: {_short(text, 200)}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Структурированная сводка БЗ — для дашборда в веб-интерфейсе.

def _recent_log_sections(project_id: str, limit: int = 10) -> list[dict]:
    """Последние секции KNOWLEDGE_LOG.md: [{stamp, entries: [str]}]."""
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
    return [s for s in sections if s["entries"] or s is sections[0]] if sections else []


def knowledge_summary(project: Project) -> dict:
    """JSON-сводка БЗ проекта: статистика, документы, гипотезы с инсайтами, журнал."""
    report_index = _report_index(project.id)
    causes, supported, refuted, insights_total = _stats(project)
    problem = next((n for n in project.nodes if n.node_type == NodeType.PROBLEM), None)
    docs = _list_docs(project.id)

    hypotheses = []
    for cause in causes:
        items = []
        for method in _methods_under(project.nodes, cause.id):
            for q in method.research_questions:
                rep = report_index.get(q.card_id) if q.card_id else None
                items.append(
                    {
                        "id": q.id,
                        "question": q.question,
                        "narrative": q.narrative or q.answer,
                        "answer": q.answer,
                        "certainty": q.certainty.value,
                        "importance": q.importance,
                        "card_id": q.card_id,
                        "method_id": method.id,
                        "method_title": method.title,
                        "report": f"reports/{rep}" if rep else None,
                    }
                )
        items.sort(key=lambda x: x["importance"], reverse=True)
        hypotheses.append(
            {
                "id": cause.id,
                "title": cause.title,
                "description": _short(cause.description, 280),
                "verdict": cause.verdict.value,
                "insights": items,
            }
        )

    doc_items = []
    for doc in docs:
        title, summary = _doc_meta(doc)
        doc_items.append(
            {
                "path": f"knowledge/{doc.name}",
                "name": doc.name,
                "title": title,
                "summary": summary,
                "generated": doc.name == GENERATED_DOC,
            }
        )

    return {
        "project_id": project.id,
        "title": project.title,
        "problem": (
            {"title": problem.title, "summary": _short(problem.description, 400)}
            if problem
            else None
        ),
        "stats": {
            "hypotheses": len(causes),
            "supported": supported,
            "refuted": refuted,
            "open": len(causes) - supported - refuted,
            "insights": insights_total,
            "docs": len(docs),
            "reports": len(report_index),
        },
        "docs": doc_items,
        "hypotheses": hypotheses,
        "log_recent": _recent_log_sections(project.id),
    }


# ---------------------------------------------------------------------------
# Журнал пополнений (KNOWLEDGE_LOG.md): автодифф против снапшота .state.json.

def _question_fingerprint(q) -> str:
    raw = "\x00".join([q.question, q.answer, q.narrative, q.certainty.value, str(q.importance)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _snapshot(project: Project, docs: list[Path]) -> dict:
    verdicts, questions = {}, {}
    for cause in _causes(project):
        verdicts[cause.id] = {"verdict": cause.verdict.value, "title": cause.title}
        for method in _methods_under(project.nodes, cause.id):
            for q in method.research_questions:
                questions[q.id] = {
                    "question": q.question,
                    "card_id": q.card_id or "",
                    "method_title": method.title,
                    "fp": _question_fingerprint(q),
                }
    return {
        "version": 1,
        "verdicts": verdicts,
        "questions": questions,
        "docs": {d.name: _doc_meta(d)[0] for d in docs if d.name != GENERATED_DOC},
    }


def _diff_entries(old: dict, new: dict, project: Project) -> list[str]:
    entries: list[str] = []
    ov, nv = old.get("verdicts", {}), new["verdicts"]
    for cid, cur in nv.items():
        prev = ov.get(cid)
        if prev is None:
            if cur["verdict"] != Verdict.OPEN.value:
                mark = VERDICT_MARK[Verdict(cur["verdict"])]
                entries.append(f"- Вердикт «{cur['title']}» (`{cid}`): {mark}")
        elif prev["verdict"] != cur["verdict"]:
            old_mark = VERDICT_MARK[Verdict(prev["verdict"])]
            new_mark = VERDICT_MARK[Verdict(cur["verdict"])]
            entries.append(f"- Вердикт «{cur['title']}» (`{cid}`): {old_mark} → {new_mark}")

    oq, nq = old.get("questions", {}), new["questions"]
    for qid, cur in nq.items():
        prev = oq.get(qid)
        src = f"метод «{_short(cur['method_title'], 60)}»"
        if cur["card_id"]:
            src += f", карточка `{cur['card_id']}`"
        if prev is None:
            entries.append(f"- Новый инсайт ({src}): «{_short(cur['question'], 120)}»")
        elif prev.get("fp") != cur["fp"]:
            entries.append(f"- Обновлён инсайт ({src}): «{_short(cur['question'], 120)}»")
    for qid, prev in oq.items():
        if qid not in nq:
            entries.append(f"- Удалён инсайт: «{_short(prev.get('question', qid), 120)}»")

    od, nd = old.get("docs", {}), new["docs"]
    for name, title in nd.items():
        if name not in od:
            entries.append(f"- Новый документ: [{title}](knowledge/{name})")
    for name, title in od.items():
        if name not in nd:
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
        idx = text.find("\n## ")
        if idx != -1:
            old_body = text[idx:]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    section = [f"\n## {stamp}", ""]
    if initial:
        section.append("_Инициализация журнала — зафиксировано текущее состояние БЗ._")
    section += entries + [""]
    path.write_text(header + "\n".join(section) + old_body, encoding="utf-8")


def write_project_knowledge(project: Project) -> Path:
    kdir = knowledge_dir(project.id)
    kdir.mkdir(parents=True, exist_ok=True)
    report_index = _report_index(project.id)

    (kdir / GENERATED_DOC).write_text(
        render_hypotheses_doc(project, report_index), encoding="utf-8"
    )

    state_path = kdir / STATE_FILE
    old_state, initial = {}, True
    if state_path.exists():
        try:
            old_state = json.loads(state_path.read_text(encoding="utf-8"))
            initial = False
        except (json.JSONDecodeError, OSError):
            pass
    new_state = _snapshot(project, _list_docs(project.id))
    entries = _diff_entries(old_state, new_state, project)
    if entries or initial:
        _append_log(project, entries, initial)
    state_path.write_text(
        json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    path = knowledge_path(project.id)
    path.write_text(render_project_knowledge(project, report_index), encoding="utf-8")
    return path
