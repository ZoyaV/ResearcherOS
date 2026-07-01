"""Бенч: аналитическое решение квадратных уравнений vs перебор по сетке.

Аналитика — дискриминант, корни по формуле, самопроверка через теорему Виета
(x1+x2 = -b/a, x1*x2 = c/a). Перебор — сканирование сетки x in [LO, HI] с шагом
STEP, корень = середина интервала со сменой знака f(x).

Использование: PYTHONPATH=. python examples/quad_bench/quad_bench.py --n 1000 --seed 42
Печатает JSON с сырыми метриками.
"""
import argparse
import json
import time
import random

GRID_LO, GRID_HI, GRID_STEP = -200.0, 200.0, 1e-2


def gen(n, seed):
    rng = random.Random(seed)
    eqs = []
    while len(eqs) < n:
        a = rng.uniform(-10, 10)
        if abs(a) < 1e-6:
            continue
        eqs.append((a, rng.uniform(-100, 100), rng.uniform(-100, 100)))
    return eqs


def solve_analytic(a, b, c):
    d = b * b - 4 * a * c
    if d < 0:
        return ()
    s = d ** 0.5
    x1 = (-b - s) / (2 * a)
    x2 = (-b + s) / (2 * a)
    return (x1, x2) if x1 <= x2 else (x2, x1)


def solve_grid(a, b, c):
    roots = []
    x = GRID_LO
    fx = a * x * x + b * x + c
    while x < GRID_HI:
        x2 = x + GRID_STEP
        fx2 = a * x2 * x2 + b * x2 + c
        if fx == 0.0:
            roots.append(x)
        elif fx * fx2 < 0:
            roots.append(x + GRID_STEP / 2)
        x, fx = x2, fx2
    return roots


def f(a, b, c, x):
    return a * x * x + b * x + c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    eqs = gen(args.n, args.seed)

    t0 = time.perf_counter()
    analytic = [solve_analytic(*eq) for eq in eqs]
    t_analytic = time.perf_counter() - t0

    t0 = time.perf_counter()
    grid = [solve_grid(*eq) for eq in eqs]
    t_grid = time.perf_counter() - t0

    n_real = 0            # уравнений с вещественными корнями
    resid_ok = 0          # из них: max|f(корень аналитики)| < 1e-9
    max_resid_analytic = 0.0
    vieta_bad = 0         # самопроверка Виета разошлась (>1e-6 относительной)
    in_range_total = 0    # истинных корней внутри сетки
    in_range_found = 0    # из них найдено перебором
    out_of_range = 0      # истинных корней за границами сетки
    grid_err_max = 0.0    # ошибка перебора на найденных корнях
    eq_full_ok = 0        # уравнений, где перебор нашёл ВСЕ корни

    for (a, b, c), roots_a, roots_g in zip(eqs, analytic, grid):
        if not roots_a:
            continue
        n_real += 1
        resid = max(abs(f(a, b, c, x)) for x in roots_a)
        max_resid_analytic = max(max_resid_analytic, resid)
        if resid < 1e-9:
            resid_ok += 1
        x1, x2 = roots_a
        scale = max(1.0, abs(b / a), abs(c / a))
        if abs(x1 + x2 + b / a) / scale > 1e-6 or abs(x1 * x2 - c / a) / scale > 1e-6:
            vieta_bad += 1
        found_here = 0
        for x in roots_a:
            if GRID_LO <= x <= GRID_HI:
                in_range_total += 1
                near = [g for g in roots_g if abs(g - x) <= GRID_STEP]
                if near:
                    in_range_found += 1
                    found_here += 1
                    grid_err_max = max(grid_err_max, min(abs(g - x) for g in near))
            else:
                out_of_range += 1
        if found_here == len(roots_a):
            eq_full_ok += 1

    print(json.dumps({
        "n_equations": args.n,
        "seed": args.seed,
        "grid": {"lo": GRID_LO, "hi": GRID_HI, "step": GRID_STEP,
                 "candidates_per_eq": int((GRID_HI - GRID_LO) / GRID_STEP) + 1},
        "t_analytic_s": round(t_analytic, 6),
        "t_grid_s": round(t_grid, 3),
        "speedup": round(t_grid / t_analytic, 1),
        "eqs_with_real_roots": n_real,
        "analytic": {"resid_lt_1e9_share": round(resid_ok / n_real, 4),
                     "max_resid": max_resid_analytic,
                     "vieta_selfcheck_failed": vieta_bad},
        "grid_search": {"true_roots_in_range": in_range_total,
                        "found_in_range": in_range_found,
                        "true_roots_out_of_range": out_of_range,
                        "eqs_all_roots_found": eq_full_ok,
                        "eqs_all_roots_found_share": round(eq_full_ok / n_real, 4),
                        "max_err_on_found": grid_err_max},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
