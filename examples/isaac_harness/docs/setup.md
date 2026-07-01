# Setup — запуск экспериментов

Среда для несущего примера (IsaacLab RL на RTX 5090). Для других проектов — свой раздел.

## Окружение

```bash
cd <корень репо ReseachOS>
source .venv/bin/activate            # Python 3.12, зависимости + isaacsim/isaaclab
export OMNI_KIT_ACCEPT_EULA=yes ACCEPT_EULA=Y PRIVACY_CONSENT=Y
export TMPDIR=$HOME/<...>/tmp_isaac  # см. gotchas.md: общий /tmp/Assets может быть занят
mkdir -p "$TMPDIR"
```

## Один прогон бенча

```bash
bash examples/isaac_harness/bench_run.sh <physics> <num_envs> <seed> <iters> <tag>
# пример: bash examples/isaac_harness/bench_run.sh newton_mjwarp 4096 42 300 h1-newton
```
`physics` — `newton_mjwarp` или `physx`. Результат: одна JSON-строка в
`~/.cockpit-jobs/bench-results.jsonl`, полный лог — `~/.cockpit-jobs/bench-run-<tag>.log`.

## Матрица прогонов (последовательно, один GPU)

```bash
nohup bash examples/isaac_harness/bench_matrix.sh > ~/.cockpit-jobs/bench-matrix-$(date +%Y%m%d-%H%M%S).log 2>&1 < /dev/null &
tail -f ~/.cockpit-jobs/bench-results.jsonl   # по строке на завершённый прогон
```

## Где что лежит

- Метрики прогонов: `~/.cockpit-jobs/bench-results.jsonl` (поля: physics, num_envs,
  seed, iters, wall_s, train_s, scene_creation_s, success_rate, mean_reward,
  position_error, total_steps, throughput_steps_s).
- Артефакты обучения rsl_rl: `IsaacLab_release_3_0/logs/rsl_rl/franka_reach/<timestamp>/`.
