# Commands — IsaacLab RL harness

Из корня engine (`ReseachOS/`). IsaacLab — субмодуль в workspace:
`koi-workspace/projects/IsaacLab_release_3_0`.

## Обучение

```bash
cd koi-workspace/projects/IsaacLab_release_3_0
./isaaclab.sh train --rl_library rsl_rl --task Isaac-Reach-Franka-v0 --headless \
  --num_envs 4096 --seed 42 --max_iterations 300 physics=newton_mjwarp
# physics=NAME — hydra-override после обычных флагов (newton_mjwarp | physx)
```

## Бенч-харнесс

```bash
bash examples/isaac_harness/bench_run.sh <physics> <num_envs> <seed> <iters> <tag>
nohup bash examples/isaac_harness/bench_matrix.sh > ~/bench-matrix.log 2>&1 &
python examples/isaac_harness/bench_parse.py <runlog> <tag> <physics> <num_envs> <seed> <iters> <wall_s>
bash examples/isaac_harness/smoke_train.sh
bash examples/isaac_harness/smoke_physx.sh
```

## Наполнить проект isaac-rl-bench

```bash
PYTHONPATH=. python examples/isaac_harness/populate_isaac_bench.py
```

См. также `docs/setup.md`, `docs/gotchas.md`.
