# Commands — KOI (продукт)

Из корня engine (`ReseachOS/`). Данные — в `KOI_WORKSPACE` (по умолчанию `../koi-workspace`).

## Сервер

```bash
./scripts/koi-serve.sh start    # API :8010 + UI :8080
./scripts/koi-serve.sh status
./scripts/koi-serve.sh stop
```

## Демо-проекты в workspace

```bash
PYTHONPATH=. python scripts/koi_seed_demo.py
```

## Гипотеза / отчёт / БЗ

```bash
PYTHONPATH=. python scripts/koi_check_hypothesis.py <project_id> <card_id>
PYTHONPATH=. python scripts/koi_check_hypothesis.py <project_id> <card_id> --ingest-only
PYTHONPATH=. python scripts/koi_done_research.py pending
PYTHONPATH=. python agent/bin/build_kb.py
```

## Agent-chat и sync

```bash
PYTHONPATH=. python scripts/koi_agent_chat.py pending
PYTHONPATH=. python scripts/koi_project_sync.py status
```

## Примеры вне продукта

| Пример | Путь |
|--------|------|
| IsaacLab RL harness | `examples/isaac_harness/` |
| Сиды demo-aggregation / ai-agents-embodied | `examples/demo_workspace/` |
| Бенч квадратных уравнений | `examples/quad_bench/` |
