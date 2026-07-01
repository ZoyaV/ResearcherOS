# Формат программ и лаборатории KOI

Организационный слой **над** KOI-проектами. Дерево гипотез и канбан остаются в `projects/<id>/project.md`.

## Иерархия

```
laboratory.md              — лаборатория (миссия, порядок программ)
programs/<id>/program.md   — исследовательская программа (список project id)
projects/<id>/project.md   — KOI-проект (как раньше)
```

Проект может входить в несколько программ. Членство задаётся в `program.md` (`projects:`) и/или в frontmatter проекта (`programs:`).

## Лаборатория (`laboratory.md`)

```yaml
---
id: zverl-koi
title: KOI Laboratory
description: Краткое описание
format: koi/laboratory/1
programs:
  - embodied-ai
  - isaac-harness
---
```

Поле `programs` задаёт порядок групп в UI и в глобальном индексе KB.

## Программа (`programs/<id>/program.md`)

```yaml
---
id: embodied-ai
title: Embodied AI agents
description: Краткое описание программы
format: koi/program/1
projects:
  - ai-agents-embodied
---
```

Тело файла (markdown после frontmatter) — стратегический вопрос программы; для людей и агентов.

## Опционально в проекте

```yaml
---
id: my-project
title: ...
programs:
  - embodied-ai
---
```

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/laboratory` | Метаданные лаборатории |
| GET | `/programs` | Список программ с project id |
| POST | `/programs` | Создать программу (`title`, опционально `description`) |
| GET | `/programs/{id}` | Программа + сводка по проектам |
| GET | `/projects/grouped` | Проекты, сгруппированные по программам |
| GET | `/projects` | Список проектов; у каждого поле `programs` |
| POST | `/projects` | Создать проект; опционально `program_id` — сразу добавить в программу |

## KB

`python agent/bin/build_kb.py` добавляет в `agent/KNOWLEDGE.md` секцию «По программам» с агрегированной таблицей.
