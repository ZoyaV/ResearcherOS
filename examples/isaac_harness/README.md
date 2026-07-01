# IsaacLab RL harness (пример)

Несущий пример для проекта `isaac-rl-bench` в workspace. **Не часть продукта KOI** —
отдельный стенд для бенчмарков Reach-Franka (Isaac Sim 6 + IsaacLab 3.0-beta2).

## Требования

- GPU с поддержкой Isaac Sim 6
- Engine: `ReseachOS/.venv` с `isaacsim` (см. `install_isaaclab.sh`)
- Workspace: субмодуль `projects/IsaacLab_release_3_0` в `koi-workspace`

## Быстрый старт

```bash
# из корня ReseachOS
bash examples/isaac_harness/install_isaaclab.sh   # долгая установка
bash examples/isaac_harness/smoke_train.sh        # короткий прогон
bash examples/isaac_harness/bench_run.sh newton_mjwarp 4096 42 300 h1-newton
```

Документация: [docs/](docs/) (setup, commands, gotchas).

Переменные: `KOI_WORKSPACE`, `TMPDIR`, `BENCH_RESULTS`, `BENCH_RUNLOG`.
