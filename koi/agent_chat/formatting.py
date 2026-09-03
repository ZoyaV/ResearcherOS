"""Answer-format rules for the ResearchOS agent-chat capability."""

from __future__ import annotations

ANSWER_FORMAT_INSTRUCTIONS = """
Answer format for the UI panel:
1. Write connected natural English that explains the subject, related facts,
   nuances, and limitations. Do not stop at one sentence.
2. Use narrative and answer from research_database; open a report only when
   details are missing.
3. End with a Sources block after a blank line:

Sources:
• Method “…” → experiment “…”
• …

List every method and experiment supporting the answer. If no experiment exists, list only the method.
""".strip()


def format_sources_block(records: list[dict]) -> str:
    """Build trailing sources list from research_database records."""
    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    for rec in records:
        method = (rec.get("method_title") or "").strip()
        exp = (
            rec.get("experiment_title")
            or (rec.get("experiment") or {}).get("card_title")
            or ""
        ).strip()
        key = (method, exp)
        if not method or key in seen:
            continue
        seen.add(key)
        if exp:
            lines.append(f"• Method “{method}” → experiment “{exp}”")
        else:
            lines.append(f"• Method “{method}”")
    if not lines:
        return ""
    return "Sources:\n" + "\n".join(lines)


def append_sources(body: str, records: list[dict]) -> str:
    text = body.strip()
    sources = format_sources_block(records)
    if not sources:
        return text
    return f"{text}\n\n{sources}"


def no_cursor_key_warning() -> str:
    return (
        "⚠️ Cursor API key is not configured.\n\n"
        "The agent can currently answer only from existing research.json conclusions. "
        "For complete answers to arbitrary questions, add the key in ResearchOS settings "
        "using the Settings button in the top bar.\n\n"
        "This is anonymous code. You cannot connect to an external resource to obtain a key."
    )
