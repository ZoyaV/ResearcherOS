"""Grounding and coverage tests for article math lessons."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Optional

from jsonschema import Draft7Validator

from koi.literature.morphology_math import (
    extract_math_occurrences,
    normalize_latex,
    validate_math_analysis,
)


ARTICLE_HTML = """
<article>
  <p>Let <math id="p1.m1" alttext="x" display="inline"><mi>x</mi></math>
  be the input, where x is input.</p>
  <p>The same <math id="p2.m1" alttext="\\displaystyle x" display="inline"><mi>x</mi></math>
  appears again.</p>
  <table id="S1.E1" class="ltx_equation">
    <tr><td><math id="S1.E1.m1" alttext="x + 1." display="block"><mi>x</mi></math></td></tr>
  </table>
</article>
"""

MORPHOLOGY = {
    "run_id": "demo",
    "nodes": [{"id": "n01"}, {"id": "n02"}],
}


def localized(en: str, ru: Optional[str] = None) -> dict[str, str]:
    return {"en": en, "ru": ru or en}


def valid_payload() -> dict[str, object]:
    return {
        "version": 1,
        "run_id": "demo",
        "source_kind": "html",
        "source_math_count": 3,
        "expressions": [
            {
                "id": "mx001",
                "note_number": 1,
                "latex": "x",
                "normalized_latex": "x",
                "kind": "symbol",
                "lesson_depth": "glossary",
                "occurrences": [
                    {
                        "source_anchor": "p1.m1",
                        "container_anchor": None,
                        "latex": "x",
                        "display": "inline",
                        "equation_number": None,
                        "section": "1 Method",
                    },
                    {
                        "source_anchor": "p2.m1",
                        "container_anchor": None,
                        "latex": "\\displaystyle x",
                        "display": "inline",
                        "equation_number": None,
                        "section": "1 Method",
                    },
                ],
                "node_ids": ["n01"],
                "symbols": [
                    {
                        "latex": "x",
                        "meaning": localized("Input"),
                        "domain": localized("Not specified"),
                        "defined_in_source": True,
                        "source_quote": "where x is input",
                    }
                ],
                "meaning": localized("Input symbol"),
                "parts": [],
                "worked_example": {
                    "title": localized("One input"),
                    "setup": localized("Take x = 2"),
                    "steps": [
                        {"latex": "x=2", "explanation": localized("Assign the input")}
                    ],
                    "result": localized("The symbol now denotes 2"),
                },
                "plots": [],
            },
            {
                "id": "mx002",
                "note_number": 2,
                "latex": "x + 1.",
                "normalized_latex": "x+1",
                "kind": "display_equation",
                "lesson_depth": "full",
                "occurrences": [
                    {
                        "source_anchor": "S1.E1.m1",
                        "container_anchor": "S1.E1",
                        "latex": "x + 1.",
                        "display": "block",
                        "equation_number": "(1)",
                        "section": "1 Method",
                    }
                ],
                "node_ids": ["n02"],
                "symbols": [
                    {
                        "latex": "x",
                        "meaning": localized("Input"),
                        "domain": localized("Real number"),
                        "defined_in_source": True,
                        "source_quote": "where x is input",
                    }
                ],
                "meaning": localized("Adds one to the input"),
                "parts": [
                    {"latex": "x", "explanation": localized("Input")},
                    {"latex": "+1", "explanation": localized("Increment")},
                ],
                "worked_example": {
                    "title": localized("Increment two"),
                    "setup": localized("Take x = 2"),
                    "steps": [
                        {"latex": "2+1=3", "explanation": localized("Add one")}
                    ],
                    "result": localized("The output is 3"),
                },
                "plots": [
                    {
                        "title": localized("Input and output"),
                        "x": {
                            "label": localized("x"),
                            "values": [0, 1, 2],
                        },
                        "y_label": localized("x + 1"),
                        "series": [
                            {
                                "label": localized("Output"),
                                "values": [1, 2, 3],
                            }
                        ],
                        "fixed_parameters": localized("None"),
                        "explanation": localized("The output rises with the input"),
                        "grounding": "derived",
                        "source_quote": None,
                    }
                ],
            },
        ],
        "coverage_gaps": [],
    }


def test_math_schema_accepts_grounded_payload() -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / ".cursor/skills/article-morphology/references/math-analysis.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    Draft7Validator(schema).validate(valid_payload())


def test_extracts_every_math_anchor_and_groups_normalized_tex() -> None:
    extracted = extract_math_occurrences(ARTICLE_HTML)
    assert len(extracted["occurrences"]) == 3
    assert extracted["missing_anchors"] == 0
    assert normalize_latex("x") == normalize_latex("\\displaystyle x")
    assert normalize_latex("x + 1.") == "x+1"


def test_valid_math_analysis_has_no_errors() -> None:
    assert validate_math_analysis(valid_payload(), MORPHOLOGY, ARTICLE_HTML) == []


def test_rejects_tex_mismatch_and_uncovered_occurrence() -> None:
    payload = valid_payload()
    payload["expressions"][0]["occurrences"][0]["latex"] = "y"
    payload["expressions"][0]["occurrences"].pop()
    errors = validate_math_analysis(payload, MORPHOLOGY, ARTICLE_HTML)
    assert any("TeX mismatch" in error for error in errors)
    assert any("uncovered math anchors" in error for error in errors)


def test_rejects_unknown_nodes_and_symbol_quotes() -> None:
    payload = valid_payload()
    payload["expressions"][0]["node_ids"] = ["n99"]
    payload["expressions"][0]["symbols"][0]["source_quote"] = "not in source"
    errors = validate_math_analysis(payload, MORPHOLOGY, ARTICLE_HTML)
    assert any("unknown node ids" in error for error in errors)
    assert any("symbol source quote was not found" in error for error in errors)


def test_rejects_missing_symbols_in_full_lesson() -> None:
    payload = valid_payload()
    payload["expressions"][1]["symbols"] = []
    errors = validate_math_analysis(payload, MORPHOLOGY, ARTICLE_HTML)
    assert any("full lesson must define symbols" in error for error in errors)


def test_rejects_plot_length_mismatch() -> None:
    payload = deepcopy(valid_payload())
    payload["expressions"][1]["plots"][0]["series"][0]["values"] = [1, 2]
    errors = validate_math_analysis(payload, MORPHOLOGY, ARTICLE_HTML)
    assert any("length/value mismatch" in error for error in errors)
