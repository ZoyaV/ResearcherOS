"""Behavior contracts for the agent-chat capability before restructuring it."""

from __future__ import annotations

from importlib import import_module

import pytest

from koi.core.models import (
    ExperimentCard,
    KanbanBoard,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
    ResearchQuestionCertainty,
)
from koi.agent_chat import auto as agent_chat_auto
from koi.agent_chat.formatting import append_sources, format_sources_block


def test_sources_block_deduplicates_records_and_keeps_experiment_title() -> None:
    records = [
        {"method_title": "Проверка", "experiment_title": "Запуск A"},
        {"method_title": "Проверка", "experiment_title": "Запуск A"},
        {"method_title": "Анализ"},
        {"method_title": ""},
    ]

    assert format_sources_block(records) == (
        "Источники:\n"
        "• Метод «Проверка» → эксперимент «Запуск A»\n"
        "• Метод «Анализ»"
    )
    assert append_sources("  Вывод.  ", records).startswith("Вывод.\n\nИсточники:")


def test_auto_answer_uses_research_narrative_and_card_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    method = Node(
        id="method-1",
        project_id="demo",
        parent_id="remediation-1",
        node_type=NodeType.METHOD,
        title="Проверка разнообразия",
        research_questions=[
            MethodResearchQuestion(
                id="rq-1",
                question="Повысилось ли разнообразие ответов?",
                narrative="Разнообразие ответов заметно повысилось.",
                answer="diversity +18%",
                certainty=ResearchQuestionCertainty.DEFINITE,
                card_id="card-1",
            )
        ],
    )
    board = KanbanBoard(
        id="board-1",
        owner_node_id=method.id,
        cards=[
            ExperimentCard(
                id="card-1",
                board_id="board-1",
                column_id="done",
                title="Diversity benchmark",
            )
        ],
    )
    project = Project(id="demo", title="Demo", nodes=[method], boards=[board])
    monkeypatch.setattr(agent_chat_auto, "load_project", lambda *_args, **_kwargs: project)

    answer = agent_chat_auto.try_auto_answer(
        "demo", "Что показала проверка разнообразия ответов?"
    )

    assert answer is not None
    assert "Разнообразие ответов заметно повысилось." in answer
    assert "diversity +18%" in answer
    assert "Метод «Проверка разнообразия»" in answer
    assert "эксперимент «Diversity benchmark»" in answer


@pytest.mark.parametrize(
    "module_name",
    (
        "koi.agent_chat.inbox_cli",
        "koi.agent_chat.worker",
    ),
)
def test_agent_chat_entry_point_imports(module_name: str) -> None:
    assert callable(import_module(module_name).main)


def test_agent_chat_api_router_imports() -> None:
    module = import_module("api.routers.agents")

    assert module.router.prefix == ""


@pytest.mark.parametrize(
    ("legacy_name", "canonical_name"),
    (
        ("koi.services.agent_chat_auto", "koi.agent_chat.auto"),
        ("koi.services.agent_chat_format", "koi.agent_chat.formatting"),
        ("koi.services.agent_chat_inbox", "koi.agent_chat.inbox"),
        ("koi.services.agent_chat_runner", "koi.agent_chat.runner"),
        ("koi.services.agent_chat_worker_ctl", "koi.agent_chat.worker"),
    ),
)
def test_service_imports_remain_compatible(
    legacy_name: str, canonical_name: str
) -> None:
    assert import_module(legacy_name) is import_module(canonical_name)
