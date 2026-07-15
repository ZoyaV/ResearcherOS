"""Import and compatibility contracts for the paper capability."""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    (
        ("koi.services.paper_catalog", "koi.paper.catalog"),
        ("koi.services.paper_comments", "koi.paper.comments"),
        ("koi.services.paper_generator", "koi.paper.generator"),
        ("koi.services.paper_inbox", "koi.paper.inbox"),
        ("koi.services.paper_page_counts", "koi.paper.page_counts"),
        ("koi.services.paper_runner", "koi.paper.runner"),
    ),
)
def test_service_imports_remain_compatible(legacy: str, canonical: str) -> None:
    assert import_module(legacy) is import_module(canonical)


@pytest.mark.parametrize(
    "module_name",
    ("koi.paper.cli", "koi.paper.inbox_cli"),
)
def test_paper_cli_imports(module_name: str) -> None:
    assert callable(import_module(module_name).main)
