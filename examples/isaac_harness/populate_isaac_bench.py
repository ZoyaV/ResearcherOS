#!/usr/bin/env python3
"""Наполнить KOI-проект isaac-rl-bench итогами матрицы H1/H2/H3.

Демонстрация цикла харнесса kb/: рабочий отчёт о прогоне → ревью по матрице решения →
инсайты в research.json + вердикты на cause-узлах + карточки в done. Идём через
модели koi и save_project(), поэтому заодно перегенерируется per-project KNOWLEDGE.md.

Запуск: PYTHONPATH=. python examples/isaac_harness/populate_isaac_bench.py
"""
from __future__ import annotations

from koi.core.models import MethodResearchQuestion as Q
from koi.core.models import ResearchQuestionCertainty as C
from koi.core.models import Verdict
from koi.adapters.repository import load_project, save_project

PID = "isaac-rl-bench"

VERDICTS = {
    "c-h1-backend": Verdict.SUPPORTED,  # Newton быстрее при равном бюджете и не хуже по качеству
    "c-h2-numenvs": Verdict.OPEN,       # throughput-часть да; sample-efficiency не дотестирована
    "c-h3-seeds": Verdict.REFUTED,      # по success_rate предсказание не сработало (потолок метрики)
}

DONE_CARDS = {"h1-run", "h2-sweep", "h3-seeds"}

INSIGHTS = {
    "m-h1": [
        Q(
            id="rq-h1-throughput",
            question="Быстрее ли Newton, чем PhysX, при равном бюджете (4096 сред, 300 итераций, seed 42)?",
            answer="throughput 546133 vs 373306 шаг/с (×1.46); wall 74 s vs 107 s; train 54 s vs 79 s.",
            narrative=(
                "Да. На равном бюджете Newton (mjwarp) даёт ~1.46× throughput "
                "(546k против 373k шаг/с) и меньший wall-clock (74 с против 107 с), "
                "чем PhysX, на RTX 5090."
            ),
            certainty=C.DEFINITE,
            importance=5,
            card_id="h1-run",
        ),
        Q(
            id="rq-h1-scene",
            question="Дешевле ли у Newton создание сцены, чем у PhysX?",
            answer="warm-кэш: 4.10 s vs 3.88 s (≈равно). Дороговизна PhysX (~287 s) — только холодный кэш ассетов, разовая.",
            narrative=(
                "На тёплом кэше ассетов — нет: оба бэкенда создают сцену за ~4 с. "
                "Большая разница (сотни секунд) у PhysX возникает только на первом, "
                "холодном прогоне (кэширование USD-ассетов) и не повторяется, поэтому "
                "к throughput тренировки её относить нельзя."
            ),
            certainty=C.DEFINITE,
            importance=3,
            card_id="h1-run",
        ),
        Q(
            id="rq-h1-quality",
            question="Не достигается ли выигрыш Newton ценой качества обучения?",
            answer="Нет: reward 0.49 vs 0.02, success_rate 1.0 vs 0.983, position_error 0.0129 vs 0.0482 (1 seed).",
            narrative=(
                "Нет. При равном бюджете Newton не уступает PhysX по качеству: награда "
                "выше (0.49 против 0.02), success_rate 1.0 против 0.983, ошибка позиции "
                "меньше. Оценка по одному сиду — по H3 для устойчивого вывода нужно 2–3 сида."
            ),
            certainty=C.TENTATIVE,
            importance=4,
            card_id="h1-run",
        ),
    ],
    "m-h2": [
        Q(
            id="rq-h2-throughput",
            question="Как throughput зависит от num_envs на Newton?",
            answer="монотонно, near-linear до лёгкого насыщения: 128→21186, 512→74473, 2048→280869, 4096→531373 шаг/с (200 iter, seed 42).",
            narrative=(
                "Throughput растёт с числом сред почти линейно и выходит на лёгкое "
                "насыщение к 4096: 21k → 74k → 281k → 531k шаг/с для 128/512/2048/4096 "
                "сред. Больше сред — выше пропускная способность и меньше wall-clock до цели."
            ),
            certainty=C.DEFINITE,
            importance=5,
            card_id="h2-sweep",
        ),
        Q(
            id="rq-h2-sample-eff",
            question="Улучшает ли рост num_envs sample-efficiency (success при равных env-шагах)?",
            answer="Не проверено корректно: фиксировали iters=200, не суммарные env-шаги; success (0.25/0.84/1.0/1.0) растёт вместе с total_steps. Нужен прогон при равных total-steps.",
            narrative=(
                "Этот свип на вопрос не отвечает: при фиксированных итерациях большие "
                "num_envs получают и больше суммарных шагов, поэтому рост success_rate "
                "(0.25→0.84→1.0→1.0) смешан с ростом бюджета. Чтобы изолировать "
                "sample-efficiency, нужен прогон с равными суммарными env-шагами, а не итерациями."
            ),
            certainty=C.TENTATIVE,
            importance=4,
            card_id="h2-sweep",
        ),
    ],
    "m-h3": [
        Q(
            id="rq-h3-sr-ceiling",
            question="Каков разброс success_rate между сидами на 150 итерациях?",
            answer="Нулевой: success_rate=1.0 у всех 5 сидов (0..4). Метрика упёрлась в потолок.",
            narrative=(
                "На этом бюджете success_rate бесполезен как различающая метрика: у всех "
                "пяти сидов он равен 1.0, разброс нулевой — метрика насыщается раньше, чем "
                "проявляется межсидовая разница."
            ),
            certainty=C.DEFINITE,
            importance=4,
            card_id="h3-seeds",
        ),
        Q(
            id="rq-h3-reward-spread",
            question="Где тогда проявляется разброс по сидам?",
            answer="В mean_reward: 0.11..0.31 по 5 сидам (mean≈0.20) и position_error 0.0267..0.0359. Мерить надёжность — reward/position_error, не success_rate.",
            narrative=(
                "Разброс по сидам виден в награде (от 0.11 до 0.31 при среднем ~0.20) и "
                "ошибке позиции, а не в success_rate. Практический вывод харнесса: на "
                "коротком бюджете надёжность оценивать по mean_reward / position_error и "
                "публиковать std по сидам."
            ),
            certainty=C.DEFINITE,
            importance=5,
            card_id="h3-seeds",
        ),
        Q(
            id="rq-h3-nseeds",
            question="Сколько сидов нужно для устойчивого вывода?",
            answer="≥2–3: reward-std (~0.08) соизмерим с долей эффекта H1; вывод по одному сиду ненадёжен.",
            narrative=(
                "Не меньше 2–3. Разброс награды по сидам (std ~0.08) соизмерим с частью "
                "эффектов, которые мы детектируем в H1/H2, поэтому вывод по одному сиду "
                "ненадёжен — это подтверждает практическую посылку H3, хотя по success_rate "
                "она формально не сработала."
            ),
            certainty=C.TENTATIVE,
            importance=4,
            card_id="h3-seeds",
        ),
    ],
}


def main() -> None:
    project = load_project(PID)
    if project is None:
        raise SystemExit(f"project {PID} not found")

    for node in project.nodes:
        if node.id in VERDICTS:
            node.verdict = VERDICTS[node.id]
        if node.id in INSIGHTS:
            node.research_questions = INSIGHTS[node.id]

    moved = 0
    for board in project.boards:
        for card in board.cards:
            if card.id in DONE_CARDS:
                card.column_id = "done"
                moved += 1

    save_project(project)
    print(f"verdicts set: {len(VERDICTS)}; cards→done: {moved}; "
          f"insights: {sum(len(v) for v in INSIGHTS.values())}")


if __name__ == "__main__":
    main()
