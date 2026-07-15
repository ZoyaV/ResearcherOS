"""Canonical and compatibility imports for remaining extracted capabilities."""

from importlib import import_module


def test_cursor_service_imports_remain_compatible() -> None:
    assert import_module("koi.services.cursor_app") is import_module("koi.cursor.app")
    assert import_module("koi.services.cursor_usage") is import_module("koi.cursor.usage")


def test_related_work_service_imports_remain_compatible() -> None:
    assert import_module("koi.services.related_work") is import_module("koi.related_work.service")
    assert import_module("koi.services.related_work_inbox") is import_module("koi.related_work.inbox")


def test_cursor_and_review_api_imports() -> None:
    assert import_module("api.routers.cursor").router.prefix == ""
    assert import_module("api.routers.review").router.prefix == ""


def test_related_work_cli_imports() -> None:
    for module_name in ("koi.related_work.cli", "koi.related_work.inbox_cli"):
        assert callable(import_module(module_name).main)
