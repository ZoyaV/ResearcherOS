---
name: koi-paper
description: >-
  Generate NeurIPS paper (LaTeX → PDF) from ResearchOS paper queue.
  Use when paper-queue.json has pending items or `koi.paper.cli pending` lists tasks.
---

# KOI: статья из UI → PDF в проекте

Пользователь нажал **«Сгенерировать статью»** в модалке «Статья» (index.html). Задача попала в `.run/paper-queue.json`.

## Когда запускать

1. В очереди есть pending Paper (`python -m koi.paper.cli pending`).
2. Paper Inbox получил `PAPER_WAKE` в `.run/logs/paper-watch.log`.
3. Пользователь вставил сообщение «ResearchOS Paper Inbox — статья `paper-…`».

```bash
ReseachOS/.venv/bin/python -m koi.paper.cli pending
```

Или статус Paper Inbox:

```bash
ReseachOS/.venv/bin/python -m koi.paper.inbox_cli pending
```

## Алгоритм

0. **Сразу** отметь задачу принятой — UI покажет «Агент работает»:

```bash
ReseachOS/.venv/bin/python -m koi.paper.cli claim <queue_id>
```

1. `context <queue_id>` — JSON с полным промптом и данными проекта (дерево гипотез, research.json, отчёты, figures).
2. Напиши статью **на английском** в LaTeX. Формат ответа **обязателен**:

```
TITLE: <concise scientific paper title in English>
===LATEX===
<LaTeX body only — abstract through bibliography, no \documentclass or \begin{document}>
```

Правила LaTeX — в поле `prompt` из context. Используй только пути к figures из списка в промпте.

3. **Обязательно** отправь результат в систему (соберёт main.tex и PDF):

```bash
ReseachOS/.venv/bin/python -m koi.paper.cli answer <queue_id> -f paper-body.txt
```

Без `claim` UI останется в «ждёт запрос». Без `answer` PDF не появится.

При ошибке компиляции скрипт вернёт ошибку — исправь LaTeX и повтори `answer` (или сообщи пользователю).

## Paper Inbox (рекомендуется)

Отдельный постоянный чат **ResearchOS Paper Inbox** в Cursor — только генерация статей.

1. Один раз: `python -m koi.paper.inbox_cli bootstrap` → вставить в чат **ResearchOS Paper Inbox**.
2. В bootstrap — фоновый `tail -f` лога с `notify_on_output` по `^PAPER_WAKE` **и** fallback loop (`AGENT_LOOP_TICK_PAPER`, каждые 5 с).
3. Watcher: `koi-serve.sh start` поднимает фоновый watcher (~1–3 с до wake в логе).
4. Кнопка «Сгенерировать статью» → очередь → Paper Inbox при wake → **claim → context → answer**.

Копировать сообщение вручную **не нужно**, если Paper Inbox настроен.

Для первой настройки — кнопка в модалке «Статья» (скопировать bootstrap → «Inbox готов»).
