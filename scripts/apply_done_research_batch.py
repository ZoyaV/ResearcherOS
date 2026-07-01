#!/usr/bin/env python3
"""Apply research questions for pending done-research queue (one-shot batch)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from koi.done_research_queue import dequeue, list_pending  # noqa: E402
from koi.models import MethodResearchQuestion as Q  # noqa: E402
from koi.models import ResearchQuestionCertainty as C  # noqa: E402
from koi.repository import load_project, update_node  # noqa: E402

UPDATES: dict[str, list[Q]] = {
    "n-c1b39d98": [
        Q(
            id="rq-oat-tok-train",
            question=(
                "Можно ли сжать непрерывные движения руки робота в короткий набор "
                "дискретных «слов» без большой потери точности?"
            ),
            narrative=(
                "Да, в основном. Токенизатор сжимает каждые 8 последовательных команд "
                "руки в 4 дискретных «слова» из словаря на 1000 вариантов и восстанавливает "
                "движение с умеренной ошибкой. Чем больше «слов» оставить, тем точнее "
                "восстановление."
            ),
            answer=(
                "OATTok val MSE 0.0247; unnorm MSE k=1..4: 2.19/2.02/2.06/1.88; "
                "81639 chunks from model_750 rollouts; card c-0d877ca8"
            ),
            certainty=C.DEFINITE,
            importance=3,
            card_id="c-0d877ca8",
        ),
        Q(
            id="rq-oat-discrete-eval",
            question=(
                "Отстаёт ли обучение с дискретными «словами» движений от обучения "
                "непрерывными командами на задаче переориентации объекта в руке?"
            ),
            narrative=(
                "Да, в проверенной конфигурации заметно. Контур с дискретными токенами "
                "технически работает, но за сопоставимый бюджет политика учится на порядок "
                "медленнее: доля успешных попыток остаётся нулевой, а суммарная награда "
                "за эпизод в разы ниже, чем у непрерывного базового варианта."
            ),
            answer=(
                "c-9ce9e601 smoke OK; c-afab669e 400 iter: return 0.84 vs baseline ~12, "
                "SR 0.000; c-4937abfd eval SR 0.000 (149 ep) vs baseline 0.069/0.026; "
                "3.2× env-steps budget"
            ),
            certainty=C.DEFINITE,
            importance=5,
            card_id="c-4937abfd",
        ),
        Q(
            id="rq-oat-tok-normalize",
            question=(
                "Снимает ли нормализация и пошаговая (а не пакетная) токенизация "
                "главный дефект сжатия движений, даже если обучение с нуля всё равно "
                "не исследует среду?"
            ),
            narrative=(
                "Частично. Нормализация и токенизация по одному шагу резко улучшают "
                "качество восстановления движений — ошибка падает почти в десять раз. "
                "Но обучение с нуля в большом дискретном словаре по-прежнему не выходит "
                "на успешные попытки: политика застревает в пассивном режиме и не тянется "
                "к цели."
            ),
            answer=(
                "z-score+T=1: FVU 0.065 vs 0.656 (T=8); round-trip ≈ expert; "
                "PPO scratch SR 0.000, return ≈ −0.6 vs baseline ~10; card c-oat-closedloop"
            ),
            certainty=C.DEFINITE,
            importance=4,
            card_id="c-oat-closedloop",
        ),
    ],
    "m-agent-dev": [
        Q(
            id="rq-agent-protocol",
            question=(
                "Может ли агент в симуляторе строго выбирать между одним вопросом "
                "оператору и одним действием, не смешивая оба формата в одном ответе?"
            ),
            narrative=(
                "Да. Парсер принимает либо вопрос, либо действия; смешанный ответ "
                "отклоняется. Расширение записи фактов в память не ломает базовый "
                "протокол общения с оператором."
            ),
            answer="action/question protocol; mixed parse rejected; to_database extension ok; card agent-prompt",
            certainty=C.DEFINITE,
            importance=3,
            card_id="agent-prompt",
        ),
        Q(
            id="rq-agent-tick",
            question=(
                "Работает ли цикл «наблюдение → вопрос оператору или действие → шаг среды» "
                "как единая инфраструктура для экспериментов?"
            ),
            narrative=(
                "Да. Клиент–серверный цикл с полным логированием траектории готов и "
                "использован для всех основных экспериментов платформы, включая проверки "
                "агента без предварительного обучения."
            ),
            answer="agent_tick + operator + full trajectory logging; all zs experiments; card agent-loop",
            certainty=C.DEFINITE,
            importance=4,
            card_id="agent-loop",
        ),
        Q(
            id="rq-agent-memory",
            question=(
                "Помогает ли единый промпт с долговременной и краткосрочной памятью "
                "агенту чаще действовать, а не только задавать вопросы?"
            ),
            narrative=(
                "Да, если факты из ответов оператора записываются обратно в память. "
                "Без этого агент в основном спрашивает (64–67% шагов — вопросы), "
                "с реинжектом фактов доля действий растёт до примерно 23–26% и выше "
                "на отдельных абляциях."
            ),
            answer="megaprompt RECIPE+NOTE; memory off 64-67% questions vs 23-26% actions; card agent-megaprompt",
            certainty=C.DEFINITE,
            importance=4,
            card_id="agent-megaprompt",
        ),
    ],
    "m-op-dev": [
        Q(
            id="rq-op-architecture",
            question=(
                "Может ли модуль «оператор» маршрутизировать вопрос агента к нужному "
                "эксперту и собирать структурированный ответ о среде?"
            ),
            narrative=(
                "Да. Реализована модульная архитектура: распознаётся намерение вопроса, "
                "подключаются эксперты, ответ оркестрируется. Оператор видит состояние "
                "среды и правила, агент по-прежнему единственный, кто выполняет действия."
            ),
            answer="4 experts + goal orchestrator; Oracle.ask; card op-arch",
            certainty=C.DEFINITE,
            importance=4,
            card_id="op-arch",
        ),
        Q(
            id="rq-op-path",
            question=(
                "Может ли оператор давать агенту подсказки навигации по карте, "
                "которую агент не видит целиком?"
            ),
            narrative=(
                "Да, технически контур готов: эксперт по пути строит маршрутные подсказки "
                "относительно положения агента. На сложных навигационных целях качество "
                "ещё заметно уступает человеку-оператору при том же агенте."
            ),
            answer="PathExpertPipeline; human vs AI operator gap on iron pickaxe; card op-path",
            certainty=C.DEFINITE,
            importance=3,
            card_id="op-path",
        ),
        Q(
            id="rq-op-knowledge",
            question=(
                "Достаточно ли разделить знания о механиках среды и записываемую "
                "агентом память, чтобы не перегружать один промпт?"
            ),
            narrative=(
                "Да. База механик среды живёт у оператора, а агент ведёт свою таблицу "
                "фактов. Формат согласован со статьёй и поддерживает долговременные "
                "рецепты и краткие заметки."
            ),
            answer="knowledge_data + companion_bench; RECIPE/NOTE memory; card op-knowledge",
            certainty=C.DEFINITE,
            importance=4,
            card_id="op-knowledge",
        ),
    ],
    "m-n-ev-ood": [
        Q(
            id="rq-ood-pilot",
            question=(
                "Готова ли цепочка данных для пилота навигационной задачи с траекториями "
                "и аугментацией неудачных переходов?"
            ),
            narrative=(
                "Да. Собраны 320 эпизодов траекторий, отобраны 3348 неудачных переходов "
                "и для каждого подготовлен аугментированный пример — объёмы согласованы "
                "для следующих этапов обучения и сравнения."
            ),
            answer="trajectory_34_29_full 320 ep; fails 3348; dif_action 3348; card ev-pilot",
            certainty=C.DEFINITE,
            importance=4,
            card_id="ev-pilot",
        ),
    ],
    "m-exoplanet-adaptation": [
        Q(
            id="rq-exo-expert-prompts",
            question=(
                "Можно ли перевести оператора на новую «оболочку» среды, сохранив ту же "
                "архитектуру ответов?"
            ),
            narrative=(
                "Да. Промпты оператора адаптированы под новую среду без смены "
                "модульной схемы экспертов."
            ),
            answer="exo-expert-prompts card done",
            certainty=C.DEFINITE,
            importance=5,
            card_id="exo-expert-prompts",
        ),
        Q(
            id="rq-exo-agent-prompts",
            question=(
                "Можно ли адаптировать промпт агента под новую среду без поломки "
                "протокола вопрос/действие?"
            ),
            narrative=(
                "Да. Агентский промпт переписан под новую оболочку; базовый контракт "
                "общения с оператором сохранён."
            ),
            answer="exo-agent-prompts card done",
            certainty=C.DEFINITE,
            importance=5,
            card_id="exo-agent-prompts",
        ),
        Q(
            id="rq-exo-ui",
            question=(
                "Можно ли заменить визуальную оболочку среды на новую тему без "
                "регрессий в отображении?"
            ),
            narrative=(
                "В основном да. Интерфейс переведён на ассеты новой темы; визуализация "
                "готова как база для сравнительных экспериментов в двух режимах. "
                "Остаётся финальная ручная проверка режима companion."
            ),
            answer="exo-planet textures in play_web/external_visualization; card exo-ui",
            certainty=C.TENTATIVE,
            importance=3,
            card_id="exo-ui",
        ),
    ],
    "m-n-rem-pretrain": [
        Q(
            id="rq-sft-diversity",
            question=(
                "Становится ли агент разнообразнее в выборе действий после обучения "
                "на примерах траекторий?"
            ),
            narrative=(
                "Да. Раньше в одной ситуации модель перебирала примерно полтора варианта "
                "действия, после обучения на примерах — около двух."
            ),
            answer="mean diversity 2.02 vs 1.46 base (step 77); card kb-sft",
            certainty=C.DEFINITE,
            importance=5,
            card_id="kb-sft",
        ),
        Q(
            id="rq-rl-transfer",
            question=(
                "Сохраняется ли это разнообразие, когда модель дальше учится в симуляторе "
                "с подкреплением?"
            ),
            narrative=(
                "Частично. После дообучения в симуляторе разнообразие не всегда держится "
                "на том же уровне, но стартовая SFT-фаза задаёт более широкую базу действий."
            ),
            answer="RL after SFT diversity transfer; card kb-rl",
            certainty=C.TENTATIVE,
            importance=4,
            card_id="kb-rl",
        ),
        Q(
            id="rq-action-space-sweep",
            question=(
                "Расширяется ли набор действий агента, если при генерации брать больше "
                "случайных вариантов на один и тот же застрявший переход?"
            ),
            narrative=(
                "Зависит от перехода и от весов модели. На части застрявших ситуаций "
                "большая область выборки открывает новые действия; на других сет не "
                "растёт даже при 256 вариантах. После обучения на примерах модель в "
                "среднем находит больше разных действий, чем базовая, особенно там, "
                "где раньше доминировало одно направление."
            ),
            answer=(
                "5 stuck transitions pilot; mean distinct N=5→256: base 1.60→2.40, "
                "step50 1.60→2.80; id6 step50 up to 6 distinct incl. craft; "
                "card kb-action-space"
            ),
            certainty=C.DEFINITE,
            importance=4,
            card_id="kb-action-space",
        ),
    ],
    "m-op-zero-shot": [
        Q(
            id="rq-op-scaling",
            question=(
                "Масштабируется ли успех агента с оператором с размером языковой модели "
                "в иерархии крафта?"
            ),
            narrative=(
                "Да. Чем крупнее модель, тем дальше агент продвигается по цепочке "
                "создания предметов при доступе к оператору."
            ),
            answer="zs-bench scaling along crafting hierarchy; card zs-bench",
            certainty=C.DEFINITE,
            importance=5,
            card_id="zs-bench",
        ),
        Q(
            id="rq-op-vs-solo",
            question=(
                "Даёт ли доступ к оператору прирост по сравнению с агентом без подсказок?"
            ),
            narrative=(
                "Да. С оператором агент исследует среду заметно активнее, чем в режиме "
                "без подсказок при том же backbone."
            ),
            answer="zs-vs-solo exploration gain; card zs-vs-solo",
            certainty=C.DEFINITE,
            importance=5,
            card_id="zs-vs-solo",
        ),
        Q(
            id="rq-op-memory-ablation",
            question=(
                "Нужна ли агенту записываемая память фактов, если оператор уже отвечает "
                "на вопросы о среде?"
            ),
            narrative=(
                "Да, критично. Без записи фактов из ответов оператора агент в основном "
                "задаёт вопросы; с памятью доля действий растёт примерно с четверти "
                "до 85–90%, и обе проверенные модели доходят до каменной кирки."
            ),
            answer=(
                "memory off 64-67% questions; on 83-90% actions, stone pickaxe; "
                "card zs-ablation"
            ),
            certainty=C.DEFINITE,
            importance=5,
            card_id="zs-ablation",
        ),
    ],
}

# Cards covered by batch method updates (for dequeue without per-card PATCH)
METHOD_CARDS: dict[str, set[str]] = {
    "n-c1b39d98": {"c-oat-closedloop", "c-4937abfd", "c-afab669e", "c-9ce9e601"},
    "m-agent-dev": {"agent-prompt", "agent-loop", "agent-megaprompt"},
    "m-op-dev": {"op-arch", "op-path", "op-knowledge"},
    "m-n-ev-ood": {"ev-pilot"},
    "m-exoplanet-adaptation": {"exo-ui"},
    "m-n-rem-pretrain": {"kb-action-space"},
    "m-op-zero-shot": {"zs-ablation"},
}


def main() -> int:
    projects_touched: set[str] = set()
    for method_id, questions in UPDATES.items():
        # find project owning this method
        from koi.adapters.project_mount import list_mounts

        for mount in list_mounts():
            project = load_project(mount.project_id, sync_reports=False)
            if project is None:
                continue
            if not any(n.id == method_id for n in project.nodes):
                continue
            update_node(project, method_id, research_questions=questions)
            projects_touched.add(mount.project_id)
            print(f"updated {mount.project_id} / {method_id}: {len(questions)} RQs")
            break
        else:
            print(f"WARN: method {method_id} not found", file=sys.stderr)

    pending = list_pending()
    completed = 0
    for item in pending:
        pid, bid, cid = item["project_id"], item["board_id"], item["card_id"]
        project = load_project(pid, sync_reports=False)
        if project is None:
            continue
        board = next((b for b in project.boards if b.id == bid), None)
        if board is None:
            continue
        method_id = board.owner_node_id
        if cid in METHOD_CARDS.get(method_id, set()):
            if dequeue(pid, bid, cid):
                completed += 1
                print(f"complete {pid} / {cid}")

    remaining = list_pending()
    print(f"projects touched: {sorted(projects_touched)}")
    print(f"completed: {completed}; remaining: {len(remaining)}")
    if remaining:
        print(remaining, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
