"""Парсер per-run лога rsl_rl → одна JSON-строка с итоговыми метриками.
Использование: bench_parse.py <runlog> <tag> <physics> <num_envs> <seed> <iters> <wall_s>
Метрики берём по ПОСЛЕДНЕМУ вхождению (финальная итерация).
"""
import json
import re
import sys

runlog, tag, physics = sys.argv[1], sys.argv[2], sys.argv[3]
num_envs, seed, iters, wall_s = (int(sys.argv[i]) for i in (4, 5, 6, 7))

txt = open(runlog, errors="replace").read()


def last_float(pattern):
    vals = re.findall(pattern, txt)
    return float(vals[-1]) if vals else None


sr = last_float(r"Metrics/success_rate:\s*([-\d.eE]+)")
rew = last_float(r"Mean reward:\s*([-\d.eE]+)")
perr = last_float(r"Metrics/ee_pose/position_error:\s*([-\d.eE]+)")
steps = last_float(r"Total steps:\s*([\d.eE]+)")

# training-only время из последнего "Time elapsed: HH:MM:SS" (без старта Isaac Sim)
te = re.findall(r"Time elapsed:\s*(\d+):(\d+):(\d+)", txt)
train_s = (int(te[-1][0]) * 3600 + int(te[-1][1]) * 60 + int(te[-1][2])) if te else None
thr = round(steps / train_s) if (steps and train_s) else None

# время создания сцены (старт симулятора + зеркалирование ассетов) — ключевой штраф PhysX
scene_s = last_float(r"Time taken for scene creation Last:\s*([\d.]+)\s*s")

rec = {
    "tag": tag, "physics": physics, "num_envs": num_envs, "seed": seed, "iters": iters,
    "wall_s": wall_s, "train_s": train_s, "scene_creation_s": scene_s,
    "success_rate": sr, "mean_reward": rew, "position_error": perr,
    "total_steps": int(steps) if steps else None,
    "throughput_steps_s": thr,
}
print(json.dumps(rec, ensure_ascii=False))
