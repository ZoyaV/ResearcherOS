"""Grounding and readability validation for article presentations."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit


METHOD_ROLES = {"method_step", "mechanism"}
RESULT_ROLES = {"result"}


def _text(value: object) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _localized(value: object) -> bool:
    return (
        isinstance(value, dict)
        and bool(_text(value.get("ru")))
        and bool(_text(value.get("en")))
    )


class _ArticleIndex(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: dict[str, dict[str, Any]] = {}
        self.stack: list[tuple[str, str]] = []
        self.all_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        element_id = attr.get("id", "")
        if element_id:
            self.elements[element_id] = {
                "tag": tag,
                "class": attr.get("class", ""),
                "attrs": attr,
                "text": [],
                "sources": [],
            }
        self.stack.append((tag, element_id))
        source = attr.get("src", "") or attr.get("data", "")
        if source:
            for _, active_id in self.stack:
                if active_id and active_id in self.elements:
                    self.elements[active_id]["sources"].append(source)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self.all_text.append(data)
        for _, element_id in self.stack:
            if element_id and element_id in self.elements:
                self.elements[element_id]["text"].append(data)

    def normalized_element_text(self, element_id: str) -> str:
        element = self.elements.get(element_id)
        return _text(" ".join(element["text"])) if element else ""

    @property
    def normalized_text(self) -> str:
        return _text(" ".join(self.all_text))


def _article_index(article_html: str) -> _ArticleIndex:
    index = _ArticleIndex()
    index.feed(str(article_html or ""))
    return index


def _node_section(node: dict[str, Any]) -> str:
    for evidence in node.get("evidence") or []:
        if isinstance(evidence, dict) and _text(evidence.get("section")):
            return _text(evidence.get("section"))
    return ""


def _section_key(section: str) -> tuple[int, tuple[int, ...], str]:
    value = _text(section)
    lower = value.lower()
    if lower.startswith("abstract"):
        return (0, (), lower)
    number = re.match(r"^(\d+(?:\.\d+)*)", value)
    if number:
        return (1, tuple(int(part) for part in number.group(1).split(".")), lower)
    if re.search(r"conclusion|summary|future work", lower):
        return (3, (), lower)
    if re.search(r"appendix|supplement|^[a-z](?:\.|\\s)", lower):
        return (4, (), lower)
    return (2, (), lower)


def _expression_map(math_analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("id")): row
        for row in math_analysis.get("expressions") or []
        if isinstance(row, dict) and row.get("id")
    }


def validate_presentation(
    payload: dict[str, Any],
    morphology: dict[str, Any],
    math_analysis: dict[str, Any],
    article_html: str,
) -> list[str]:
    """Validate node coverage, source grounding, ordering, math, figures and tables."""
    errors: list[str] = []
    morphology_run_id = str(morphology.get("run_id") or "")
    if payload.get("morphology_run_id") != morphology_run_id:
        errors.append("morphology_run_id does not match morphology.json")

    nodes = [
        node for node in morphology.get("nodes") or [] if isinstance(node, dict)
    ]
    node_by_id = {
        str(node.get("id")): node for node in nodes if str(node.get("id") or "")
    }
    expressions = _expression_map(math_analysis)
    article = _article_index(article_html)
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        return [*errors, "slides must be a non-empty array"]

    slide_ids: set[str] = set()
    node_slide_ids: list[str] = []
    linked_slides: dict[str, list[dict[str, Any]]] = {
        node_id: [] for node_id in node_by_id
    }
    expression_ids: set[str] = set()
    figure_ids: set[str] = set()
    table_ids: set[str] = set()

    covers = [slide for slide in slides if isinstance(slide, dict) and slide.get("kind") == "cover"]
    if len(covers) != 1 or slides[0].get("kind") != "cover":
        errors.append("presentation must start with exactly one cover slide")

    current_node_id = ""
    for slide_index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            errors.append(f"slide {slide_index} must be an object")
            continue
        slide_id = str(slide.get("id") or "")
        if not slide_id or slide_id in slide_ids:
            errors.append(f"duplicate or empty slide id: {slide_id!r}")
        slide_ids.add(slide_id)
        if not _localized(slide.get("title")) or not _localized(slide.get("body")):
            errors.append(f"{slide_id}: title and body must contain ru and en")
        for language in ("ru", "en"):
            if len(_text((slide.get("body") or {}).get(language))) > 360:
                errors.append(f"{slide_id}: {language} body exceeds 360 characters")

        node_ids = slide.get("node_ids")
        if not isinstance(node_ids, list) or len(node_ids) > 1:
            errors.append(f"{slide_id}: node_ids must contain at most one node")
            continue
        node_id = str(node_ids[0]) if node_ids else ""
        kind = str(slide.get("kind") or "")
        if kind == "cover":
            if node_id:
                errors.append(f"{slide_id}: cover must not reference a node")
            continue
        if not node_id or node_id not in node_by_id:
            errors.append(f"{slide_id}: unknown or missing node id {node_id!r}")
            continue
        linked_slides[node_id].append(slide)
        if kind == "node":
            current_node_id = node_id
            node_slide_ids.append(node_id)
        elif current_node_id != node_id:
            errors.append(f"{slide_id}: detail slide must follow its node slide")

        node = node_by_id[node_id]
        section = _text(slide.get("section_anchor"))
        expected_section = _node_section(node)
        if section != expected_section:
            errors.append(
                f"{slide_id}: section {section!r} does not match node section {expected_section!r}"
            )
        quote = _text(slide.get("evidence_quote"))
        node_quotes = {
            _text(item.get("quote"))
            for item in node.get("evidence") or []
            if isinstance(item, dict) and _text(item.get("quote"))
        }
        if quote and quote not in node_quotes:
            errors.append(f"{slide_id}: evidence quote is not attached to {node_id}")
        if quote and quote not in article.normalized_text:
            errors.append(f"{slide_id}: evidence quote was not found in article.html")

        visual = slide.get("visual")
        if not isinstance(visual, dict):
            continue
        visual_kind = str(visual.get("kind") or "")
        if visual_kind == "math":
            for expression_id in visual.get("expression_ids") or []:
                expression_id = str(expression_id)
                expression_ids.add(expression_id)
                if expression_id not in expressions:
                    errors.append(f"{slide_id}: unknown expression {expression_id}")
        elif visual_kind == "algorithm":
            orders: list[int] = []
            for step in visual.get("steps") or []:
                if not isinstance(step, dict):
                    errors.append(f"{slide_id}: algorithm step must be an object")
                    continue
                orders.append(step.get("order"))
                anchor = str(step.get("source_anchor") or "")
                if anchor not in article.elements:
                    errors.append(f"{slide_id}: unknown algorithm anchor {anchor!r}")
                expression_id = step.get("expression_id")
                if expression_id:
                    expression_id = str(expression_id)
                    expression_ids.add(expression_id)
                    expression = expressions.get(expression_id)
                    if not expression:
                        errors.append(f"{slide_id}: unknown expression {expression_id}")
                    else:
                        anchors = {
                            str(item.get("source_anchor"))
                            for item in expression.get("occurrences") or []
                            if isinstance(item, dict)
                        }
                        if anchor not in anchors:
                            errors.append(
                                f"{slide_id}: {anchor} does not belong to {expression_id}"
                            )
            if orders != list(range(1, len(orders) + 1)):
                errors.append(f"{slide_id}: algorithm step order must be consecutive")
        elif visual_kind == "figure":
            figure_id = str(visual.get("figure_id") or "")
            figure_ids.add(figure_id)
            anchor = str(visual.get("source_anchor") or "")
            element = article.elements.get(anchor)
            if not element or "ltx_figure" not in str(element.get("class") or ""):
                errors.append(f"{slide_id}: unknown article figure {anchor!r}")
            caption = _text(visual.get("source_caption"))
            if element and caption not in article.normalized_element_text(anchor):
                errors.append(f"{slide_id}: figure caption is not grounded in {anchor}")
            src = str(visual.get("src") or "")
            if urlsplit(src).scheme != "https":
                errors.append(f"{slide_id}: figure src must use HTTPS")
            if element:
                source_names = {
                    source.rsplit("/", 1)[-1] for source in element.get("sources") or []
                }
                if source_names and src.rsplit("/", 1)[-1] not in source_names:
                    errors.append(f"{slide_id}: figure src does not match {anchor}")
        elif visual_kind == "table":
            table_id = str(visual.get("table_id") or "")
            table_ids.add(table_id)
            anchor = str(visual.get("source_anchor") or "")
            element = article.elements.get(anchor)
            if not element or "ltx_table" not in str(element.get("class") or ""):
                errors.append(f"{slide_id}: unknown article table {anchor!r}")
            caption = _text(visual.get("source_caption"))
            if element and caption not in article.normalized_element_text(anchor):
                errors.append(f"{slide_id}: table caption is not grounded in {anchor}")
            cell_ids: set[str] = set()
            cell_support: dict[str, set[str]] = {}
            for row in visual.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                row_anchor = str(row.get("source_anchor") or "")
                if row_anchor not in article.elements:
                    errors.append(f"{slide_id}: unknown table row {row_anchor!r}")
                for cell in row.get("cells") or []:
                    if not isinstance(cell, dict):
                        continue
                    cell_anchor = str(cell.get("source_anchor") or "")
                    cell_ids.add(cell_anchor)
                    if cell_anchor not in article.elements:
                        errors.append(f"{slide_id}: unknown table cell {cell_anchor!r}")
                    elif _text(cell.get("value")) != article.normalized_element_text(
                        cell_anchor
                    ):
                        errors.append(f"{slide_id}: value mismatch at {cell_anchor}")
                    cell_support[cell_anchor] = {
                        str(value) for value in cell.get("supports_node_ids") or []
                    }
            highlights = {str(value) for value in visual.get("highlight_cell_ids") or []}
            if not highlights or not highlights.issubset(cell_ids):
                errors.append(f"{slide_id}: highlighted cells must belong to table slice")
            support_ids = set().union(
                *(cell_support.get(cell_id, set()) for cell_id in highlights)
            )
            if node_id not in support_ids:
                errors.append(f"{slide_id}: highlighted values do not support {node_id}")

    expected_order = [
        str(node.get("id"))
        for _, node in sorted(
            enumerate(nodes),
            key=lambda pair: (
                _section_key(_node_section(pair[1])),
                pair[0],
            ),
        )
    ]
    if node_slide_ids != expected_order:
        errors.append(
            f"node slides are not in article order: {node_slide_ids}, expected {expected_order}"
        )
    if len(node_slide_ids) != len(set(node_slide_ids)):
        errors.append("a node has more than one main node slide")
    if set(node_slide_ids) != set(node_by_id):
        errors.append("main node slides must cover every graph node exactly once")

    for node_id, node in node_by_id.items():
        visuals = [
            slide.get("visual")
            for slide in linked_slides.get(node_id, [])
            if isinstance(slide.get("visual"), dict)
        ]
        kinds = {str(visual.get("kind") or "") for visual in visuals}
        role = str(node.get("role") or "")
        if role in METHOD_ROLES and not kinds.intersection({"math", "algorithm"}):
            errors.append(f"{node_id}: method node needs a math or algorithm slide")
        if role in RESULT_ROLES and "table" not in kinds:
            errors.append(f"{node_id}: result node needs a grounded table slide")

    coverage = payload.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        expected_coverage = {
            "node_ids": set(node_by_id),
            "expression_ids": expression_ids,
            "figure_ids": figure_ids,
            "table_ids": table_ids,
        }
        for field, expected in expected_coverage.items():
            actual = {str(value) for value in coverage.get(field) or []}
            if actual != expected:
                errors.append(
                    f"coverage.{field}={sorted(actual)}, expected {sorted(expected)}"
                )
    return errors


def validate_presentation_critique(
    critique: dict[str, Any],
    presentation: dict[str, Any],
) -> list[str]:
    """Require a passing per-slide readability audit with concrete measurements."""
    errors: list[str] = []
    presentation_run_id = str(presentation.get("presentation_run_id") or "")
    if critique.get("presentation_run_id") != presentation_run_id:
        errors.append("critique presentation_run_id does not match presentation")
    if critique.get("pass") is not True:
        errors.append("presentation critique did not pass")

    slide_by_id = {
        str(slide.get("id")): slide
        for slide in presentation.get("slides") or []
        if isinstance(slide, dict) and slide.get("id")
    }
    audits = critique.get("slides")
    if not isinstance(audits, list):
        return [*errors, "critique slides must be an array"]
    audit_by_id = {
        str(audit.get("slide_id")): audit
        for audit in audits
        if isinstance(audit, dict) and audit.get("slide_id")
    }
    if len(audit_by_id) != len(audits):
        errors.append("critique contains duplicate or invalid slide audits")
    if set(audit_by_id) != set(slide_by_id):
        errors.append("critique must cover every presentation slide exactly once")

    for slide_id, slide in slide_by_id.items():
        audit = audit_by_id.get(slide_id)
        if not audit:
            continue
        checks = audit.get("checks")
        if not isinstance(checks, dict):
            errors.append(f"{slide_id}: missing readability checks")
            continue
        if audit.get("pass") is not True or audit.get("issues"):
            errors.append(f"{slide_id}: readability audit did not pass")
        if checks.get("overflow") is not False:
            errors.append(f"{slide_id}: slide content overflows")
        if not isinstance(checks.get("minimum_font_px"), (int, float)) or checks.get(
            "minimum_font_px"
        ) < 16:
            errors.append(f"{slide_id}: minimum font size is below 16px")

        visual = slide.get("visual")
        visual_kind = visual.get("kind") if isinstance(visual, dict) else ""
        if visual_kind == "figure":
            width_fraction = checks.get("image_width_fraction")
            if not isinstance(width_fraction, (int, float)) or width_fraction < 0.55:
                errors.append(f"{slide_id}: figure occupies less than 55% slide width")
            if int(visual.get("natural_width") or 0) < 480:
                errors.append(f"{slide_id}: figure natural width is below 480px")
            if visual.get("contains_text"):
                min_text = checks.get("minimum_image_text_px")
                if not isinstance(min_text, (int, float)) or min_text < 14:
                    errors.append(f"{slide_id}: figure text is below 14px")
        if visual_kind == "table":
            if checks.get("table_values_grounded") is not True:
                errors.append(f"{slide_id}: table values were not grounded")
            if checks.get("highlights_support_claim") is not True:
                errors.append(f"{slide_id}: table highlights do not support the claim")
    return errors


__all__ = [
    "METHOD_ROLES",
    "RESULT_ROLES",
    "validate_presentation",
    "validate_presentation_critique",
]
