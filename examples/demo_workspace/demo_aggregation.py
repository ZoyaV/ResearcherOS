"""Example seed: demo-aggregation project."""

from koi.models import (
    DEFAULT_KANBAN_COLUMNS,
    ExperimentCard,
    KanbanBoard,
    Node,
    NodeType,
    Project,
)


def build_demo_project() -> Project:
    project = Project(
        id="demo-aggregation",
        title="Нестабильная экспрессия рекомбинантного белка",
        description="Набросок: от проблемы к экспериментам через дерево гипотез.",
    )

    problem = Node(
        id="n-problem",
        project_id=project.id,
        node_type=NodeType.PROBLEM,
        title="Низкий выход целевого белка в культуре HEK293",
        description="После трансфекции <30% ожидаемой концентрации на 72 ч.",
    )

    cause_misfold = Node(
        id="n-cause-misfold",
        project_id=project.id,
        parent_id=problem.id,
        node_type=NodeType.CAUSE,
        title="Причина: агрегация из-за неправильного фолдинга",
        description="Белок образует инклюзии в цитоплазме.",
    )

    cause_toxic = Node(
        id="n-cause-toxic",
        project_id=project.id,
        parent_id=problem.id,
        node_type=NodeType.CAUSE,
        title="Причина: токсичность для клеток",
        description="Высокая экспрессия снижает жизнеспособность популяции.",
    )

    ev_viability = Node(
        id="n-ev-viability",
        project_id=project.id,
        parent_id=cause_toxic.id,
        node_type=NodeType.CAUSE_EVIDENCE,
        title="Доказательство: viability assay 72 ч",
    )

    ev_fold = Node(
        id="n-ev-fold",
        project_id=project.id,
        parent_id=cause_misfold.id,
        node_type=NodeType.CAUSE_EVIDENCE,
        title="Доказательство: ThT-флуоресценция и TEM инклюзий",
    )

    rem_chaperone = Node(
        id="n-rem-chaperone",
        project_id=project.id,
        parent_id=cause_misfold.id,
        node_type=NodeType.REMEDIATION,
        title="Устранение: ко-экспрессия шаперонов HSP70/40",
    )

    method_fold = Node(
        id="m-n-ev-fold",
        project_id=project.id,
        parent_id=ev_fold.id,
        node_type=NodeType.METHOD,
        title="ThT и TEM",
        description="Флуоресценция ThT и электронная микроскопия инклюзий.",
    )

    method_chaperone = Node(
        id="m-n-rem-chaperone",
        project_id=project.id,
        parent_id=rem_chaperone.id,
        node_type=NodeType.METHOD,
        title="Ко-трансфекция шаперонов",
    )

    method_viability = Node(
        id="m-n-ev-viability",
        project_id=project.id,
        parent_id=ev_viability.id,
        node_type=NodeType.METHOD,
        title="Viability assay",
    )

    board_fold = KanbanBoard(
        id="board-ev-fold",
        owner_node_id=method_fold.id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[
            ExperimentCard(
                board_id="board-ev-fold",
                column_id="running",
                title="ThT time-course",
                description="Сравнить с контрольным GFP.",
            ),
            ExperimentCard(
                board_id="board-ev-fold",
                column_id="backlog",
                title="TEM инклюзий",
                description="n=3 биологических повторности.",
            ),
        ],
    )

    board_chaperone = KanbanBoard(
        id="board-rem-chaperone",
        owner_node_id=method_chaperone.id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[
            ExperimentCard(
                board_id="board-rem-chaperone",
                column_id="running",
                title="Ко-трансфекция HSP70",
                description="Дозировка 1:1 и 1:2 с целевым конструктом.",
            ),
        ],
    )

    board_viability = KanbanBoard(
        id="board-ev-viability",
        owner_node_id=method_viability.id,
        columns=list(DEFAULT_KANBAN_COLUMNS),
        cards=[
            ExperimentCard(
                board_id="board-ev-viability",
                column_id="backlog",
                title="MTT / Trypan blue",
                description="Сравнить с пустым вектором.",
            ),
        ],
    )

    project.nodes = [
        problem,
        cause_misfold,
        cause_toxic,
        ev_viability,
        ev_fold,
        rem_chaperone,
        method_fold,
        method_chaperone,
        method_viability,
    ]
    project.boards = [board_fold, board_chaperone, board_viability]
    return project
