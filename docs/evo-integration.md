# Headless Evo в ResearchOS

ResearchOS использует Evo как backend поиска по реализации эксперимента. UI
Evo не запускается: карточка ResearchOS остаётся источником постановки,
отчёта и verdict, а ResearchOS Monitor показывает нормализованный статус,
score, gates и traces.

## Контракт карточки

Добавьте в description карточки:

```text
evo_run: runs/evo/<run_id>
live_log: runs/evo/<run_id>/stdout.log
```

Evo traces можно писать в тот же каталог через `EVO_TRACES_DIR`. Файл
`state.json` — небольшой ResearchOS-слой, который содержит `status`, `pid`,
`returncode` и `summary`; `experiments.json` используется Monitor для списка
веток. Внешний dashboard Evo для этого не нужен.

Evo должен работать в code repo проекта. `tree/<repo>/koi-structure` остаётся
отдельным worktree с исследовательскими материалами и не передаётся Evo как
рабочая директория.

## Train/test правило

Benchmark обязан разделять train и held-out test до запуска поиска. Gates должны
проверять отсутствие пересечения идентификаторов, наличие обеих частей и
считать итоговую метрику только на test. Score, полученный на train, нельзя
использовать как научный verdict.
