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
KOI/.venv/bin/python -m koi.projects.sync_cli status
KOI/.venv/bin/python -m koi.projects.sync_cli pull
KOI/.venv/bin/python -m koi.projects.sync_cli pending-push
KOI/.venv/bin/python -m koi.projects.sync_cli complete-push --all
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

Скрипты: `agents/skills/koi-project-sync/hooks/`. Подключение: скопируй
`agents/cursor-hooks.json` → `.cursor/hooks.json`.

| Hook | Скрипт | Поведение |
|------|--------|-----------|
| `sessionStart` | `koi-project-sync-session.sh` | pull + `additional_context` при очереди push или проблемах |
| `stop` | `koi-project-sync-stop.sh` | если ≥30 мин — followup pull; если очередь push — followup commit+push |

## Связанные скиллы

- `koi-project-onboard` — после attach пишет в `tree/<repo>/koi-structure/` и
  вызывает `install_cli` + первый `push` (§6c); дальше обычный sync здесь
- `koi-done-research` — после вывода проверь push
- `koi-dev-server` — API пишет в mounts, очередь push пополняется автоматически
- `loop` — фоновый pull каждые 30 мин

## Sibling repos (`tree/<repo>/koi-structure` + orphan branch)

Канон: working copy research-данных — `tree/<repo>/koi-structure/` (git worktree
на `git_sync_branch`, обычно `koi/research`). Code-репо — sibling `<repo>/`.

Если layout ещё не `tree/`:

```bash
python -m koi.projects.install_cli status
python -m koi.projects.install_cli install <repo>   # или migrate
```

Для проектов с `git_repo: true` и `git_sync_branch` каноничный sync CLI:

```bash
python -m koi.projects.sync_cli init-sync-branch --project-id <id>
python -m koi.projects.sync_cli push --project-id <id>
python -m koi.projects.sync_cli pull --project-id <id>
python -m koi.projects.sync_cli status
```

Push/pull работают с mount `koi_root` (под `tree/`); не копируй дерево обратно
в code-ветку.
