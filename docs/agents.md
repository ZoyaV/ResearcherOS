# Агенты в ResearchOS

ResearchOS рассчитан на выполнение исследовательских задач агентами разных
сред: Cursor, Codex, Claude и другими. Общие инструкции репозитория находятся в
[`AGENTS.md`](../AGENTS.md), а содержательные skills — в [`agents/skills/`](../agents/skills/).

## Layout проектов

```text
workspace/
├── ReseachOS/                         # engine
├── tree/<repo>/koi-structure/         # исследование (ветка koi/research)
└── <repo>/                            # код (любая ветка)
```

Установка / миграция: `python -m koi.projects.install_cli install <repo>`.
Discovery входит в папку `tree` и ищет `*/koi-structure/project.md`.

## Где находится источник правды

| Сущность | Расположение |
|---|---|
| Дерево исследования и канбан | `tree/<repo>/koi-structure/project.md` (legacy: `<repo>/koi-structure/`) |
| Исследовательские выводы | `…/koi-structure/research.json` |
| Публичные и рабочие отчёты | `…/koi-structure/reports/` |
| Курируемые знания | `…/koi-structure/knowledge/*.md` |
| Генерируемый индекс знаний | `KNOWLEDGE.md`, обновляет `koi/knowledge` |
| Содержательные agent skills | `agents/skills/` |

## Skills

- `koi-project-onboard` — подключить code-репо: диалог + prose + дерево в
  `tree/<repo>/koi-structure/`; затем `install_cli` (orphan `koi/research`);
- `koi-grill-experiment` — спроектировать карточку эксперимента до прогона;
- `koi-execute-card` — выполнить карточку эксперимента;
- `koi-card-autoresearch` — длинный прогон с ролями Руководитель / Исследователь / Дебаггер;
- `koi-report-review` — подготовить и проверить отчёт;
- `koi-done-research` — сформулировать вывод завершённого эксперимента;
- `koi-agent-chat` — ответить на вопрос из UI;
- `koi-knowledge-curator` — синтезировать накопленные знания;
- `koi-paper` и `koi-related-work` — подготовить материалы статьи;
- `koi-project-sync` — синхронизировать `tree/<repo>/koi-structure` с веткой sync;
- `koi-prose-style` — проверить человекочитаемый текст.

Шаблоны и правила хранятся рядом с тем skill, который их применяет. Отдельного
глобального каталога стандартов нет.

## Cursor

`.cursor/hooks/` содержит только интеграционные hooks. Ссылки в
`.cursor/skills/` дают Cursor доступ к тем же общим skills без копирования.
Developer skills самого ResearchOS физически остаются в `.cursor/skills/`.

Подробнее: [исследовательский workflow](research-workflow.md),
[доменная модель](domain-model.md), [Inbox](agent-chat-inbox.md),
[ADR-001 discovery](adr-001-project-discovery.md).
