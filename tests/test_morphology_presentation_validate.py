"""Validation tests for graph-grounded article presentations."""

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator

from koi.literature.morphology_presentation_validate import (
    validate_presentation,
    validate_presentation_critique,
)


ARTICLE = """
<article class="ltx_document">
  <section id="abstract"><p>The paper starts from a concrete problem.</p></section>
  <section id="S2">
    <p>The method applies a grounded operation.</p>
    <math id="S2.E1.m1" alttext="y=x+1"><mi>y</mi></math>
    <figure id="S2.F1" class="ltx_figure">
      <img src="assets/diagram.png" width="800" height="500">
      <figcaption>Figure 1 Method overview</figcaption>
    </figure>
  </section>
  <section id="S3">
    <p>The measured result improves.</p>
    <figure id="S3.T1" class="ltx_table">
      <figcaption>Table 1 Results</figcaption>
      <table>
        <tr id="S3.T1.r1"><td id="S3.T1.r1.c1">Model A</td><td id="S3.T1.r1.c2">92.0</td></tr>
        <tr id="S3.T1.r2"><td id="S3.T1.r2.c1">Model B</td><td id="S3.T1.r2.c2">88.0</td></tr>
      </table>
    </figure>
  </section>
  <section id="conclusion"><p>The conclusion states a limitation.</p></section>
</article>
"""

MORPHOLOGY = {
    "run_id": "morph-run",
    "nodes": [
        {
            "id": "n01",
            "role": "problem",
            "statement": "Problem",
            "evidence": [
                {
                    "quote": "The paper starts from a concrete problem.",
                    "section": "Abstract",
                }
            ],
        },
        {
            "id": "n02",
            "role": "mechanism",
            "statement": "Method",
            "evidence": [
                {
                    "quote": "The method applies a grounded operation.",
                    "section": "2 Method",
                }
            ],
        },
        {
            "id": "n03",
            "role": "result",
            "statement": "Result",
            "evidence": [
                {
                    "quote": "The measured result improves.",
                    "section": "3 Results",
                }
            ],
        },
        {
            "id": "n04",
            "role": "limitation",
            "statement": "Limitation",
            "evidence": [
                {
                    "quote": "The conclusion states a limitation.",
                    "section": "Conclusion",
                }
            ],
        },
    ],
    "edges": [],
}

MATH_ANALYSIS = {
    "run_id": "morph-run",
    "expressions": [
        {
            "id": "mx001",
            "latex": "y=x+1",
            "occurrences": [{"source_anchor": "S2.E1.m1"}],
        }
    ],
}


def loc(en: str, ru: str) -> dict[str, str]:
    return {"en": en, "ru": ru}


def slide(
    slide_id: str,
    kind: str,
    node_id: str,
    section: str,
    quote: str,
    visual=None,
) -> dict:
    return {
        "id": slide_id,
        "kind": kind,
        "node_ids": [node_id] if node_id else [],
        "section_anchor": section or None,
        "title": loc(slide_id, slide_id),
        "body": loc("Short grounded explanation.", "Краткое объяснение."),
        "evidence_quote": quote or None,
        "visual": visual,
    }


def valid_presentation() -> dict:
    return {
        "version": 1,
        "presentation_run_id": "presentation-run",
        "morphology_run_id": "morph-run",
        "default_language": "ru",
        "slides": [
            slide("cover", "cover", "", "", ""),
            slide(
                "slide_n01",
                "node",
                "n01",
                "Abstract",
                "The paper starts from a concrete problem.",
            ),
            slide(
                "slide_n02",
                "node",
                "n02",
                "2 Method",
                "The method applies a grounded operation.",
            ),
            slide(
                "slide_n02_math",
                "math",
                "n02",
                "2 Method",
                "The method applies a grounded operation.",
                {"kind": "math", "expression_ids": ["mx001"]},
            ),
            slide(
                "slide_n02_figure",
                "figure",
                "n02",
                "2 Method",
                "The method applies a grounded operation.",
                {
                    "kind": "figure",
                    "figure_id": "f01",
                    "source_anchor": "S2.F1",
                    "src": "https://arxiv.org/html/paper/assets/diagram.png",
                    "source_caption": "Figure 1 Method overview",
                    "explanation": loc("Method overview.", "Схема метода."),
                    "natural_width": 800,
                    "natural_height": 500,
                    "contains_text": True,
                    "render_width_fraction": 0.7,
                },
            ),
            slide(
                "slide_n03",
                "node",
                "n03",
                "3 Results",
                "The measured result improves.",
            ),
            slide(
                "slide_n03_table",
                "table",
                "n03",
                "3 Results",
                "The measured result improves.",
                {
                    "kind": "table",
                    "table_id": "t01",
                    "source_anchor": "S3.T1",
                    "source_caption": "Table 1 Results",
                    "columns": ["Model", "Score"],
                    "rows": [
                        {
                            "label": "Model A",
                            "source_anchor": "S3.T1.r1",
                            "cells": [
                                {
                                    "source_anchor": "S3.T1.r1.c2",
                                    "column": "Score",
                                    "value": "92.0",
                                    "emphasis": "best",
                                    "supports_node_ids": ["n03"],
                                }
                            ],
                        },
                        {
                            "label": "Model B",
                            "source_anchor": "S3.T1.r2",
                            "cells": [
                                {
                                    "source_anchor": "S3.T1.r2.c2",
                                    "column": "Score",
                                    "value": "88.0",
                                    "emphasis": "neutral",
                                    "supports_node_ids": [],
                                }
                            ],
                        },
                    ],
                    "highlight_cell_ids": ["S3.T1.r1.c2"],
                    "explanation": loc(
                        "The highlighted score supports the claim.",
                        "Выделенное значение подтверждает тезис.",
                    ),
                },
            ),
            slide(
                "slide_n04",
                "node",
                "n04",
                "Conclusion",
                "The conclusion states a limitation.",
            ),
        ],
        "coverage": {
            "node_ids": ["n01", "n02", "n03", "n04"],
            "expression_ids": ["mx001"],
            "figure_ids": ["f01"],
            "table_ids": ["t01"],
        },
    }


def valid_critique(presentation: dict) -> dict:
    audits = []
    for row in presentation["slides"]:
        visual = row.get("visual") or {}
        kind = visual.get("kind")
        audits.append(
            {
                "slide_id": row["id"],
                "pass": True,
                "checks": {
                    "overflow": False,
                    "minimum_font_px": 18,
                    "image_width_fraction": 0.7 if kind == "figure" else None,
                    "minimum_image_text_px": 16 if kind == "figure" else None,
                    "table_values_grounded": True if kind == "table" else None,
                    "highlights_support_claim": True if kind == "table" else None,
                },
                "issues": [],
            }
        )
    return {
        "version": 1,
        "presentation_run_id": "presentation-run",
        "pass": True,
        "slides": audits,
    }


def test_presentation_and_critique_schemas_accept_valid_payloads() -> None:
    root = Path(__file__).resolve().parents[2]
    reference = (
        root
        / ".cursor/skills/article-morphology-presentation/references"
    )
    presentation_schema = json.loads(
        (reference / "presentation.schema.json").read_text(encoding="utf-8")
    )
    critique_schema = json.loads(
        (reference / "presentation-critique.schema.json").read_text(encoding="utf-8")
    )
    Draft7Validator.check_schema(presentation_schema)
    Draft7Validator.check_schema(critique_schema)
    Draft7Validator(presentation_schema).validate(valid_presentation())
    Draft7Validator(critique_schema).validate(
        valid_critique(valid_presentation())
    )


def test_valid_presentation_is_fully_grounded() -> None:
    payload = valid_presentation()
    assert validate_presentation(payload, MORPHOLOGY, MATH_ANALYSIS, ARTICLE) == []
    assert validate_presentation_critique(valid_critique(payload), payload) == []


def test_rejects_missing_node_and_wrong_article_order() -> None:
    payload = valid_presentation()
    payload["slides"] = [
        payload["slides"][0],
        *payload["slides"][5:],
        *payload["slides"][1:5],
    ]
    errors = validate_presentation(payload, MORPHOLOGY, MATH_ANALYSIS, ARTICLE)
    assert any("article order" in error for error in errors)


def test_rejects_method_without_math_or_algorithm() -> None:
    payload = valid_presentation()
    payload["slides"] = [
        row
        for row in payload["slides"]
        if row["id"] != "slide_n02_math"
    ]
    payload["coverage"]["expression_ids"] = []
    errors = validate_presentation(payload, MORPHOLOGY, MATH_ANALYSIS, ARTICLE)
    assert any("method node needs" in error for error in errors)


def test_rejects_unverified_result_table_values() -> None:
    payload = valid_presentation()
    table = next(
        row for row in payload["slides"] if row["id"] == "slide_n03_table"
    )
    table["visual"]["rows"][0]["cells"][0]["value"] = "99.9"
    table["visual"]["rows"][0]["cells"][0]["supports_node_ids"] = []
    errors = validate_presentation(payload, MORPHOLOGY, MATH_ANALYSIS, ARTICLE)
    assert any("value mismatch" in error for error in errors)
    assert any("do not support n03" in error for error in errors)


def test_rejects_unreadable_figure_critique() -> None:
    payload = valid_presentation()
    critique = valid_critique(payload)
    audit = next(
        row for row in critique["slides"] if row["slide_id"] == "slide_n02_figure"
    )
    audit["checks"]["image_width_fraction"] = 0.4
    audit["checks"]["minimum_image_text_px"] = 10
    errors = validate_presentation_critique(critique, payload)
    assert any("less than 55%" in error for error in errors)
    assert any("below 14px" in error for error in errors)
