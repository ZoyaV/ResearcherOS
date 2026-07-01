---
name: koi-project-sync
description: >-
  Auto-sync KOI projects/ with git: commit and push significant changes (experiments
  done, reports, research questions, kanban); pull on Cursor startup and every 30
  minutes. Use when sync-push queue has items, after KOI workflows, on session
  start, or when the user mentions git sync, push, or pull for projects.
---

# KOI: синхронизация projects/ с git

Репозиторий — корень `KOI/` (remote `origin`). Данные проектов — только `projects/<id>/`.

## Когда запускать

| Триггер | Действие |
|---------|----------|
| `sessionStart` hook | **pull** (см. ниже) |
| `stop` hook, прошло ≥30 мин | **pull** снова |
| Очередь push не пуста или dirty `projects/` | **commit + push** |
| После `koi-done-research`, сохранения отчёта, переноса в done | проверь `pending-push` |
| Пользователь просит синхронизировать | оба направления |

При старте сессии с KOI **сначала pull, потом очереди** (done-research, agent-chat, push).

## CLI

```bash
KOI/.venv/bin/python KOI/scripts/koi_project_sync.py status
KOI/.venv/bin/python KOI/scripts/koi_project_sync.py pull
KOI/.venv/bin/python KOI/scripts/koi_project_sync.py pending-push
KOI/.venv/bin/python KOI/scripts/koi_project_sync.py complete-push --all
```

## Pull (входящие изменения)

1. `pull` — скрипт делает `git fetch` и `git pull --ff-only`, если origin впереди и нет незакоммиченных файлов в `projects/`.
2. Если pull заблокирован (локальные изменения + remote впереди) — **сначала push-workflow** для локальных правок, затем pull. При конфликте — сообщи пользователю, не делай force.
3. На первой сессии дня: если нет фонового loop — запусти мониторинг раз в 30 минут (скилл `loop`):

```bash
# Loop every 30m: koi-project-sync pull
```

## Push (исходящие изменения)

### Значимые изменения (коммитить)

- карточка перешла в **done** или сменила колонку
- новый/обновлённый **отчёт** (`reports/`)
- **research.json** / research_questions
- новая карточка, узел дерева, правки канбана или project.md

### Не коммитить

- `.run/`, `.venv/`, `__pycache__/`
- код KOI (`koi/`, `api/`, `web/`) — только если пользователь явно правил платформу
- секреты (`.env`)

### Workflow

1. `pending-push` — очередь `.run/sync-push-queue.json` + `git status projects/`.
2. Если `needs_push` — сгруппируй по проектам, stage только `projects/`:

```bash
cd KOI
git add projects/<project_id>/
git status
```

3. Commit message (русский или английский, кратко):

```
projects(<id>): <суть>

- <деталь из очереди>
```

Примеры:
- `projects(ai-agents-embodied): эксперимент Diversity-only → done`
- `projects(isaaclab-dexsuite-reorient): отчёт baseline PPO`

4. Push (только по явному триггеру скилла или очереди — пользователь настроил авто-sync):

```bash
cd KOI && git push origin HEAD
```

5. `complete-push --all` после успешного push.

### Если push отклонён (non-fast-forward)

Сначала `pull`, разреши конфликты в `projects/`, затем push. Без `--force`.

## Очередь push

API и агент добавляют записи при значимых изменениях. Поля: `project_id`, `reason`, `detail`.

Приоритет: после обработки done-research / отчёта — сразу проверь push, чтобы выводы ушли в remote.

## Cursor hooks (ResearchOS workspace)

| Hook | Скрипт | Поведение |
|------|--------|-----------|
| `sessionStart` | `koi-project-sync-session.sh` | pull + `additional_context` при очереди push или проблемах |
| `stop` | `koi-project-sync-stop.sh` | если ≥30 мин — followup pull; если очередь push — followup commit+push |

## Связанные скиллы

- `koi-done-research` — после вывода проверь push
- `koi-dev-server` — API пишет в `projects/`, очередь push пополняется автоматически
- `loop` — фоновый pull каждые 30 мин
