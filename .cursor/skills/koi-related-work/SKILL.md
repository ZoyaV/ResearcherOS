---
name: koi-related-work
description: >-
  Generate Related Works markdown from the ResearchOS RelatedWork page queue.
  Use when related-work-queue.json has pending items or koi_related_work.py pending
  lists tasks.
---

# KOI: Related Work из UI → ответ в RelatedWork

Пользователь нажал **Related Work** на странице RelatedWork (localhost:8080/literature.html). Задача попала в `.run/related-work-queue.json`.

## Когда запускать

1. В очереди есть pending Related Work (`koi_related_work.py pending`).
2. Literature Inbox получил `RELATED_WORK_WAKE` в `.run/logs/related-work-watch.log`.
3. Пользователь вставил сообщение «ResearchOS Literature Inbox — Related Work `rw-…`».

```bash
ReseachOS/.venv/bin/python ReseachOS/scripts/koi_related_work.py pending
```

Или статус Literature Inbox:

```bash
ReseachOS/.venv/bin/python ReseachOS/scripts/koi_related_work_inbox.py pending
```

## Алгоритм

0. **Сразу** отметь задачу принятой — UI покажет «Агент работает» и таймер:

```bash
ReseachOS/.venv/bin/python ReseachOS/scripts/koi_related_work.py claim <queue_id>
```

1. `context <queue_id>` — JSON с полным промптом и метаданными кластеров.
2. Напиши раздел **Related Works** в markdown:
   - заголовок `## Related Works`
   - 2–5 абзацев, синтез выбранных кластеров
   - только факты из промпта, без выдуманных статей
3. **Обязательно** сохрани ответ в UI:

```bash
ReseachOS/.venv/bin/python ReseachOS/scripts/koi_related_work.py answer <queue_id> -f related-work.md
```

Без `claim` страница останется в «ждёт запрос». Без `answer` черновик не появится.

## Literature Inbox (рекомендуется)

Отдельный постоянный чат **ResearchOS Literature Inbox** в Cursor — только Related Work (не путать с Chat Inbox для вопросов).

1. Один раз: `python scripts/koi_related_work_inbox.py bootstrap` → вставить в чат **ResearchOS Literature Inbox**.
2. В bootstrap — фоновый `tail -f` лога с `notify_on_output` по `^RELATED_WORK_WAKE` **и** fallback loop (`AGENT_LOOP_TICK_RELATED_WORK`, каждые 3 с) + `koi_related_work_inbox.py pending`.
3. Watcher: `koi-serve.sh start` поднимает фоновый watcher (~1–3 с до wake в логе).
4. Кнопка **Related Work** → очередь → Literature Inbox при wake → **claim → context → answer**.

Копировать сообщение вручную **не нужно**, если Literature Inbox настроен.

Для первой настройки — кнопка «Скопировать сообщение» на literature.html (текст не показывается, только инструкция).
