"""Validation helpers for grounded article math lessons."""

from __future__ import annotations

import math
import re
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
from typing import Any

try:
    from latex2mathml.converter import convert as _convert_latex
except ImportError:  # Optional only for environments that have not installed requirements.
    _convert_latex = None


_LATEX_SPACING_RE = re.compile(r"\\(?:,|;|!|quad|qquad)")
_TRAILING_MATH_PUNCTUATION_RE = re.compile(r"[,.]+$")


def normalize_latex(value: str) -> str:
    """Normalize harmless TeX formatting for occurrence grouping."""
    text = str(value or "").strip()
    text = text.replace(r"\displaystyle", "")
    text = _LATEX_SPACING_RE.sub("", text)
    text = re.sub(r"\s+", "", text)
    return _TRAILING_MATH_PUNCTUATION_RE.sub("", text)


class _MathHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.math: list[dict[str, str]] = []
        self.missing_anchors = 0
        self._container_stack: list[tuple[str, str]] = []
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        anchor = attr.get("id", "")
        if tag in {"table", "tbody"} and anchor:
            self._container_stack.append((tag, anchor))
        if tag != "math":
            return
        latex = attr.get("alttext", "")
        if not anchor or not latex:
            self.missing_anchors += 1
            return
        container = self._container_stack[-1][1] if self._container_stack else ""
        self.math.append(
            {
                "source_anchor": anchor,
                "container_anchor": container,
                "latex": latex,
                "display": "block" if attr.get("display") == "block" else "inline",
            }
        )

    def handle_endtag(self, tag: str) -> None:
        if self._container_stack and self._container_stack[-1][0] == tag:
            self._container_stack.pop()

    def handle_data(self, data: str) -> None:
        self._text.append(data)

    @property
    def plain_text(self) -> str:
        return re.sub(r"\s+", " ", unescape(" ".join(self._text))).strip()


def extract_math_occurrences(article_html: str) -> dict[str, object]:
    parser = _MathHTMLParser()
    parser.feed(str(article_html or ""))
    return {
        "occurrences": parser.math,
        "missing_anchors": parser.missing_anchors,
        "plain_text": parser.plain_text,
    }


def _localized_complete(value: object) -> bool:
    return (
        isinstance(value, dict)
        and bool(str(value.get("en") or "").strip())
        and bool(str(value.get("ru") or "").strip())
    )


def _finite_numbers(values: object) -> bool:
    return (
        isinstance(values, list)
        and len(values) >= 2
        and all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            for value in values
        )
    )


@lru_cache(maxsize=4096)
def latex_to_mathml(latex: str, display: str = "inline") -> str:
    """Convert trusted lesson TeX to inert MathML for the web response."""
    if _convert_latex is None or not str(latex or "").strip():
        return ""
    try:
        return _convert_latex(str(latex), display=display)
    except Exception:
        return ""


def add_rendered_mathml(payload: dict[str, object]) -> dict[str, object]:
    """Add derived MathML fields without changing the persisted artifact."""
    for expression in payload.get("expressions") or []:
        if not isinstance(expression, dict):
            continue
        display = "block" if expression.get("kind") == "display_equation" else "inline"
        expression["_mathml"] = latex_to_mathml(
            str(expression.get("latex") or ""),
            display,
        )
        for symbol in expression.get("symbols") or []:
            if isinstance(symbol, dict):
                symbol["_mathml"] = latex_to_mathml(str(symbol.get("latex") or ""))
        for part in expression.get("parts") or []:
            if isinstance(part, dict):
                part["_mathml"] = latex_to_mathml(str(part.get("latex") or ""))
        example = expression.get("worked_example")
        if isinstance(example, dict):
            for step in example.get("steps") or []:
                if isinstance(step, dict):
                    step["_mathml"] = latex_to_mathml(str(step.get("latex") or ""))
    return payload


def validate_math_analysis(
    payload: dict[str, object],
    morphology: dict[str, object],
    article_html: str,
) -> list[str]:
    """Return deterministic contract errors; an empty list means valid."""
    errors: list[str] = []
    if payload.get("run_id") != morphology.get("run_id"):
        errors.append("run_id does not match morphology")
    extracted = extract_math_occurrences(article_html)
    source_rows = extracted["occurrences"]
    assert isinstance(source_rows, list)
    source_by_anchor = {
        str(row["source_anchor"]): row for row in source_rows if isinstance(row, dict)
    }
    source_text = str(extracted["plain_text"])
    missing_anchors = int(extracted["missing_anchors"])
    if missing_anchors:
        errors.append(f"article has {missing_anchors} math elements without id or alttext")

    source_count = payload.get("source_math_count")
    if source_count != len(source_rows):
        errors.append(
            f"source_math_count={source_count!r}, expected {len(source_rows)}"
        )

    expressions = payload.get("expressions")
    if not isinstance(expressions, list):
        return [*errors, "expressions must be an array"]

    graph_node_ids = {
        str(node.get("id"))
        for node in morphology.get("nodes") or []
        if isinstance(node, dict) and node.get("id")
    }
    expression_ids: set[str] = set()
    note_numbers: set[int] = set()
    covered_anchors: list[str] = []

    for expression in expressions:
        if not isinstance(expression, dict):
            errors.append("expression must be an object")
            continue
        expression_id = str(expression.get("id") or "")
        if not expression_id or expression_id in expression_ids:
            errors.append(f"duplicate or empty expression id: {expression_id!r}")
        expression_ids.add(expression_id)

        note_number = expression.get("note_number")
        if (
            not isinstance(note_number, int)
            or isinstance(note_number, bool)
            or note_number < 1
            or note_number in note_numbers
        ):
            errors.append(f"{expression_id}: invalid or duplicate note_number")
        else:
            note_numbers.add(note_number)

        latex = str(expression.get("latex") or "")
        normalized = normalize_latex(latex)
        if expression.get("normalized_latex") != normalized:
            errors.append(f"{expression_id}: normalized_latex does not match latex")

        kind = expression.get("kind")
        lesson_depth = expression.get("lesson_depth")
        if kind == "symbol" and lesson_depth != "glossary":
            errors.append(f"{expression_id}: symbol must use glossary lesson_depth")
        if kind in {"inline_expression", "display_equation"} and lesson_depth != "full":
            errors.append(f"{expression_id}: compound expression must use full lesson_depth")

        occurrences = expression.get("occurrences")
        if not isinstance(occurrences, list) or not occurrences:
            errors.append(f"{expression_id}: occurrences must not be empty")
            continue
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                errors.append(f"{expression_id}: occurrence must be an object")
                continue
            anchor = str(occurrence.get("source_anchor") or "")
            covered_anchors.append(anchor)
            source = source_by_anchor.get(anchor)
            if source is None:
                errors.append(f"{expression_id}: unknown source anchor {anchor!r}")
                continue
            occurrence_latex = str(occurrence.get("latex") or "")
            if normalize_latex(occurrence_latex) != normalize_latex(str(source["latex"])):
                errors.append(f"{expression_id}: TeX mismatch at {anchor}")
            if normalize_latex(occurrence_latex) != normalized:
                errors.append(f"{expression_id}: occurrence {anchor} belongs to another group")

        invalid_nodes = [
            node_id
            for node_id in expression.get("node_ids") or []
            if str(node_id) not in graph_node_ids
        ]
        if invalid_nodes:
            errors.append(f"{expression_id}: unknown node ids {invalid_nodes}")

        if not _localized_complete(expression.get("meaning")):
            errors.append(f"{expression_id}: meaning must contain en and ru")

        symbols = expression.get("symbols")
        parts = expression.get("parts")
        if lesson_depth == "full" and (not isinstance(symbols, list) or not symbols):
            errors.append(f"{expression_id}: full lesson must define symbols")
        if lesson_depth == "full" and (not isinstance(parts, list) or not parts):
            errors.append(f"{expression_id}: full lesson must explain expression parts")
        for part in parts or []:
            if not isinstance(part, dict) or not _localized_complete(part.get("explanation")):
                errors.append(f"{expression_id}: incomplete bilingual expression part")
        for symbol in symbols or []:
            if not isinstance(symbol, dict):
                errors.append(f"{expression_id}: symbol must be an object")
                continue
            if not _localized_complete(symbol.get("meaning")) or not _localized_complete(
                symbol.get("domain")
            ):
                errors.append(f"{expression_id}: incomplete bilingual symbol")
            quote = symbol.get("source_quote")
            if symbol.get("defined_in_source"):
                if not quote or str(quote) not in source_text:
                    errors.append(f"{expression_id}: symbol source quote was not found")
            elif quote is not None:
                errors.append(f"{expression_id}: undefined symbol must not have source_quote")

        example = expression.get("worked_example")
        if not isinstance(example, dict) or not example.get("steps"):
            errors.append(f"{expression_id}: worked example must contain steps")
        elif not all(
            _localized_complete(example.get(field))
            for field in ("title", "setup", "result")
        ):
            errors.append(f"{expression_id}: incomplete bilingual worked example")
        else:
            for step in example.get("steps") or []:
                if not isinstance(step, dict) or not _localized_complete(
                    step.get("explanation")
                ):
                    errors.append(f"{expression_id}: incomplete bilingual example step")

        for plot_index, plot in enumerate(expression.get("plots") or []):
            if not isinstance(plot, dict):
                errors.append(f"{expression_id}: plot {plot_index} must be an object")
                continue
            x_values = (plot.get("x") or {}).get("values") if isinstance(plot.get("x"), dict) else None
            plot_localized = [
                plot.get("title"),
                plot.get("y_label"),
                plot.get("fixed_parameters"),
                plot.get("explanation"),
                (plot.get("x") or {}).get("label")
                if isinstance(plot.get("x"), dict)
                else None,
            ]
            plot_localized.extend(
                series.get("label")
                for series in plot.get("series") or []
                if isinstance(series, dict)
            )
            if not all(_localized_complete(value) for value in plot_localized):
                errors.append(f"{expression_id}: plot {plot_index} is not bilingual")
            if not _finite_numbers(x_values):
                errors.append(f"{expression_id}: plot {plot_index} has invalid x values")
                continue
            for series_index, series in enumerate(plot.get("series") or []):
                y_values = series.get("values") if isinstance(series, dict) else None
                if not _finite_numbers(y_values) or len(y_values) != len(x_values):
                    errors.append(
                        f"{expression_id}: plot {plot_index} series {series_index} length/value mismatch"
                    )
            quote = plot.get("source_quote")
            if plot.get("grounding") == "quoted" and (
                not quote or str(quote) not in source_text
            ):
                errors.append(f"{expression_id}: quoted plot evidence was not found")

    if len(covered_anchors) != len(set(covered_anchors)):
        errors.append("a math occurrence is assigned to more than one expression")
    if note_numbers != set(range(1, len(expressions) + 1)):
        errors.append("note_number values must be consecutive from 1")
    missing = sorted(set(source_by_anchor) - set(covered_anchors))
    extra = sorted(set(covered_anchors) - set(source_by_anchor))
    if missing:
        errors.append(f"uncovered math anchors: {missing}")
    if extra:
        errors.append(f"unknown covered math anchors: {extra}")
    return errors


__all__ = [
    "add_rendered_mathml",
    "extract_math_occurrences",
    "latex_to_mathml",
    "normalize_latex",
    "validate_math_analysis",
]
