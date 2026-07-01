# Документация ReseachOS

Два входа — по аудитории:

| Аудитория | Каталог | С чего начать |
|-----------|---------|---------------|
| **Человек** | [human/](human/) | [getting-started.md](human/getting-started.md) |
| **Агент IDE** | [../agent/](../agent/) | [AGENTS.md](../agent/AGENTS.md) |

## Человек (`docs/human/`)

Путеводители, форматы данных, как устроена база знаний.

## Агент (`docs/agent/` + `agent/`)

- **`agent/AGENTS.md`** — роль агента, очереди, рабочие циклы, форматные ворота.
- **`agent/onboarding/`** — карта репо, команды CLI.
- **`agent/templates/`**, **`agent/process.md`** — шаблоны отчётов и матрица ревью.
- **`docs/agent/`** — доменная модель, inbox-чат, прочая техсправка.

Скиллы-плейбуки: `.cursor/skills/*/SKILL.md`.

## Совместимость

Старые пути в корне `docs/` — symlink: `GETTING_STARTED.md`, `PROJECT_FORMAT.md`, `domain-model.md` и т.д.
