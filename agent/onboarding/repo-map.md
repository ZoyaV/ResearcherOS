# Repo-map — где что лежит

## Engine (`ReseachOS/`)

```
ReseachOS/
  api/         FastAPI: api/main.py + api/routers/* (по доменам)
  web/         статический фронт; web/api.js → :8010
  koi/         доменное ядро (core / adapters / services)
  standards/   шаблон и правила публичных отчётов
  agent/       AGENTS.md, onboarding, templates, process.md, bin/build_kb.py
  kb/          symlink → agent/
  docs/
    human/     getting-started, project-format, program-format, knowledge-base
    agent/     domain-model, agent-chat-inbox
  scripts/     CLI продукта
  examples/    demo_workspace, isaac_harness — не продукт
```

Корень: `README.md` (человек). Инструкции агента: `agent/AGENTS.md`.

## Workspace (`../koi-workspace/` — `KOI_WORKSPACE`)

```
koi-workspace/
  laboratory.md   порядок программ
  programs/       program.md
  projects/       один проект = projects/<id>/:
                    project.md, research.json, reports/, knowledge/, paper_reviews/
  library/        library.csv — библиотека литературы
  agent_bundles/  пакеты paper review для IDE
  .run/           runtime (очереди, pid, sync-state)
```

Модель данных KOI: дерево `problem → cause → {cause_evidence | remediation} → method`;
канбан только у `method`; вердикт (`open|supported|refuted`) на узле-гипотезе (`cause`).

Доменная модель подробнее: `docs/agent/domain-model.md`.
