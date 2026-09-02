# Headless Evo в ResearchOS

Полный пользовательский сценарий: `koi-grill-experiment` проектирует claim и
карточку в `backlog`, `koi-evo-card` запускает Evo и live-stream, а
`koi-report-review` оформляет результат в отчёт. Карточка появляется в
Monitor сразу после перехода в `running` и следующего polling; не нужно ждать
первого score.

ResearchOS использует Evo как backend поиска по реализации эксперимента. UI
Evo не встраивается: карточка ResearchOS остаётся источником постановки,
отчёта и verdict, а ResearchOS Monitor показывает нормализованный статус,
score, gates, гипотезу, решение и графики из Evo worktree.

## Контракт карточки

Добавьте в description карточки:

```text
evo_run: .evo/run_<id>
live_log: .evo/dashboard.log
```

Для синхронизации текста и артефактов во время прогона запустите рядом с Evo:

```bash
PYTHONPATH=/path/to/ResearchOS uv run python -m koi.evolution.watch \
  <project_id> <board_id> <card_id> .evo/run_<id>
```

Watcher обновляет `evo-live.md` в отчёте карточки и копирует SVG/PNG в его
`assets/`. GET-путь Monitor остаётся read-only и при этом сразу показывает
те же поля через polling.

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
