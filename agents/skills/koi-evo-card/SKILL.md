---
name: koi-evo-card
description: >-
  Run a ResearchOS kanban card through the headless Evo backend, expose its
  live hypotheses, checks, scores and plots in Monitor, and hand the results
  to the report-review workflow.
---

# KOI: запуск карточки через Evo

Этот skill подключается после `koi-grill-experiment` и вместе с
`koi-execute-card` ведёт один эксперимент от карточки до отчёта. Evo UI не
нужен: его `.evo/run_<id>` — backend, ResearchOS Monitor — рабочее окно.

## Перед стартом

1. У карточки должны быть claim, одна основная метрика, пороги
   `supported/refuted/open`, команда benchmark, train/test правило, gate и
   SMART-подзадачи в §3. Если этого нет — вернуться к `koi-grill-experiment`.
2. В description карточки зафиксировать:

   ```text
   evo_run: .evo/run_<id>
   live_log: .evo/dashboard.log
   ```

3. Если карточка в `backlog`, сначала перевести её в `running` по правилам
   `koi-execute-card`. После этого она появляется в Monitor при следующем
   polling (обычно до 3 секунд); для Evo-панели достаточно существующего
   `graph.json`.

## Запуск и live-поток

Инициализировать Evo в code repository проекта, а не в `koi-structure`:

```bash
evo init --name '<name>' --target <target> \
  --benchmark '<benchmark command>' --metric max \
  --gate '<gate command>' --host generic \
  --commit-strategy tracked-only
evo new --parent root -m '<hypothesis>'
evo run <exp_id> --timeout 120 --i-staged-new-files yes
```

Параллельно держать ResearchOS stream актуальным:

```bash
PYTHONPATH=/path/to/ResearchOS uv run python -m koi.evolution.watch \
  <project_id> <board_id> <card_id> .evo/run_<id>
```

Watcher не подменяет Evo: он только читает `graph.json` и check/gate JSON,
пишет `evo-live.md` в отчёт карточки и копирует графики в `assets/`.

## После прогона

1. Проверить в Monitor hypothesis, candidate, score, checks и graph artifact.
2. Перенести результаты в §4/§5 отчёта по `koi-report-review`; не выдавать
   score сам по себе за научный вывод.
3. После PASS критика результатов отметить §3, перевести карточку
   `running → done`, затем применить `koi-done-research`.

Если Evo не может закоммитить из-за runtime-файлов, сначала проверить, что
это действительно warm state; для нового файла использовать
`--i-staged-new-files yes`, не добавляя runtime state в исследовательский
коммит.
