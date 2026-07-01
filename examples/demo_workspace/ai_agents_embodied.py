"""Example seed: ai-agents-embodied project."""

from koi.models import (
    DEFAULT_KANBAN_COLUMNS,
    ExperimentCard,
    KanbanBoard,
    MethodResearchQuestion,
    Node,
    NodeType,
    Project,
    ResearchQuestionCertainty,
)


def build_ai_agents_project() -> Project:
    project = Project(
        id="ai-agents-embodied",
        title="Низкая производительность AI-AGENTS в воплощённых средах",
        description="Шаблон: OOD-среды и гипотезы улучшения exploration и оператора.",
    )

    problem = Node(
        id="n-problem",
        project_id=project.id,
        node_type=NodeType.PROBLEM,
        title="Низкая производительность AI-AGENTS в воплощённых средах",
        description="Агенты плохо обобщают на новые embodied-среды и теряют эффективность принятия решений.",
    )

    cause_ood = Node(
        id="n-cause-ood",
        project_id=project.id,
        parent_id=problem.id,
        node_type=NodeType.CAUSE,
        title="OOD-среды: новые механики, представления и промпты",
        description=(
            "Под-проблема: при смене механик, визуальных представлений или формулировок промптов "
            "агент принимает решения неэффективно — падает success rate и растёт число бесполезных действий."
        ),
    )

    ev_ood = Node(
        id="n-ev-ood",
        project_id=project.id,
        parent_id=cause_ood.id,
        node_type=NodeType.CAUSE_EVIDENCE,
        title="Доказательство: метрики деградации в OOD-бенчмарке",
        description="Сравнить in-distribution vs OOD: success rate, steps-to-goal, action entropy.",
    )

    rem_pretrain = Node(
        id="n-rem-pretrain",
        project_id=project.id,
        parent_id=cause_ood.id,
        node_type=NodeType.REMEDIATION,
        title="Exploration через pretraining: выровнять top-5 LLM",
        description=(
            "Гипотеза: LLM ранжирует больше вариантов, чем попадает в top-5 при семплировании. "
            "Сделать top-k действий равновероятными после pretraining на разнообразии траекторий."
        ),
    )

    rem_operator = Node(
        id="n-rem-operator",
        project_id=project.id,
        parent_id=cause_ood.id,
        node_type=NodeType.REMEDIATION,
        title="Оператор: помощник в принятии решений",
        description=(
            "Гипотеза: отдельный модуль «Оператор» уточняет план, фильтрует действия "
            "и снижает ошибки при OOD-сдвиге."
        ),
    )

    method_ood = Node(
        id="m-n-ev-ood",
        project_id=project.id,
        parent_id=ev_ood.id,
        node_type=NodeType.METHOD,
        title="OOD-бенчмарк",
    )

    method_pretrain = Node(
        id="m-n-rem-pretrain",
        project_id=project.id,
        parent_id=rem_pretrain.id,
        node_type=NodeType.METHOD,
        title="Расширение области действий через SFT обучение",
        description="SFT на разнообразии действий → diversity на test → RL.",
        research_questions=[
            MethodResearchQuestion(
                id="rq-sft-diversity",
                question=(
                    "Становится ли агент разнообразнее в выборе действий "
                    "после обучения на примерах траекторий?"
                ),
                answer="mean diversity 2.02 vs 1.46 base (step 77)",
                narrative=(
                    "Да. Раньше в одной и той же ситуации модель в среднем перебирала "
                    "примерно полтора варианта действия, после обучения на примерах — около двух. "
                    "То есть она чаще рассматривает несколько разных ходов, а не повторяет один и тот же."
                ),
                certainty=ResearchQuestionCertainty.DEFINITE,
                importance=5,
                card_id="kb-sft",
            ),
            MethodResearchQuestion(
                id="rq-rl-transfer",
                question=(
                    "Сохраняется ли это разнообразие, когда модель дальше учится "
                    "в симуляторе по награде за успех?"
                ),
                answer="SR(SFT+RL) ≈ SR(BASE+RL) во время PPO",
                narrative=(
                    "Пока не видно. При дообучении в среде доля успешных попыток у модели "
                    "с предварительным обучением на примерах примерно такая же, как у модели без него, "
                    "а разнообразие действий в самой симуляции не выросло."
                ),
                certainty=ResearchQuestionCertainty.TENTATIVE,
                importance=4,
                card_id="kb-rl",
            ),
        ],
    )

    method_op_dev = Node(
        id="m-op-dev",
        project_id=project.id,
        parent_id=rem_operator.id,
        node_type=NodeType.METHOD,
        title="Разработка оператора",
        description="Oracle: intent, эксперты, path pipeline, knowledge base.",
    )

    method_agent_dev = Node(
        id="m-agent-dev",
        project_id=project.id,
        parent_id=rem_operator.id,
        node_type=NodeType.METHOD,
        title="Разработка агента",
        description="ActiveAgent: промпт Q/Act, agent_tick, megaprompt.",
    )

    method_op_zero_shot = Node(
        id="m-op-zero-shot",
        project_id=project.id,
        parent_id=rem_operator.id,
        node_type=NodeType.METHOD,
        title="Zero-shot агент с оператором",
        description="Companion bench: SR и абляции без дообучения.",
    )

    board_ood = KanbanBoard(
        id="board-ev-ood",
        owner_node_id=method_ood.id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[
            ExperimentCard(
                board_id="board-ev-ood",
                column_id="backlog",
                title="OOD suite: 3 среды × 3 сдвига",
                description="Механики / представления / промпты.",
            ),
            ExperimentCard(
                board_id="board-ev-ood",
                column_id="backlog",
                title="Логи action entropy",
                description="Сравнить ID и OOD на одном чекпоинте.",
            ),
        ],
    )

    board_pretrain = KanbanBoard(
        id="board-rem-pretrain",
        owner_node_id=method_pretrain.id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[
            ExperimentCard(
                board_id="board-rem-pretrain",
                column_id="running",
                title="Pretrain на смеси траекторий",
                description="Uniform policy head over top-5 tokens.",
            ),
            ExperimentCard(
                board_id="board-rem-pretrain",
                column_id="backlog",
                title="Измерить coverage скрытых действий",
                description="KL между полным logits и top-5 sample.",
            ),
        ],
    )

    board_op_dev = KanbanBoard(
        id="board-op-dev",
        owner_node_id=method_op_dev.id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[
            ExperimentCard(
                board_id="board-op-dev",
                column_id="backlog",
                title="Архитектура Oracle: intent → эксперты → ответ",
                description="Дизайн роутинга и контракт ask/answer.",
            ),
            ExperimentCard(
                board_id="board-op-dev",
                column_id="backlog",
                title="Path expert: подсказки навигации на карте",
                description="Helper + path pipeline, лимит длины ответа.",
            ),
            ExperimentCard(
                board_id="board-op-dev",
                column_id="backlog",
                title="Durable knowledge base для механик Craftext",
                description="MegaPrompt knowlage_data, companion_bench seed.",
            ),
        ],
    )

    board_agent_dev = KanbanBoard(
        id="board-agent-dev",
        owner_node_id=method_agent_dev.id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[
            ExperimentCard(
                board_id="board-agent-dev",
                column_id="backlog",
                title="Промпт агента и парсинг вопросов / действий",
                description="agent_prompt.txt, ask_operator, consecutive questions.",
            ),
            ExperimentCard(
                board_id="board-agent-dev",
                column_id="backlog",
                title="Цикл agent_tick: наблюдение → оператор → шаг среды",
                description="WebSocket, ActiveAgent, Oracle.ask.",
            ),
            ExperimentCard(
                board_id="board-agent-dev",
                column_id="backlog",
                title="Megaprompt: формат наблюдения и контекст памяти",
                description="dialog config, action history, inventory.",
            ),
        ],
    )

    board_op_zero_shot = KanbanBoard(
        id="board-op-zero-shot",
        owner_node_id=method_op_zero_shot.id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[
            ExperimentCard(
                board_id="board-op-zero-shot",
                column_id="backlog",
                title="Companion bench: baseline-кампания на нескольких LLM",
                description="Parallel agents, cycles, leaderboard.",
            ),
            ExperimentCard(
                board_id="board-op-zero-shot",
                column_id="backlog",
                title="SR и число вопросов: с оператором vs solo-агент",
                description="interaction_mode oracle vs none, OOD задачи.",
            ),
            ExperimentCard(
                board_id="board-op-zero-shot",
                column_id="backlog",
                title="Абляция экспертов и памяти оператора",
                description="allowed_experts, knowledge_source base/own.",
            ),
        ],
    )

    project.nodes = [
        problem,
        cause_ood,
        ev_ood,
        rem_pretrain,
        rem_operator,
        method_ood,
        method_pretrain,
        method_op_dev,
        method_agent_dev,
        method_op_zero_shot,
    ]
    project.boards = [
        board_ood,
        board_pretrain,
        board_op_dev,
        board_agent_dev,
        board_op_zero_shot,
    ]
    return project
