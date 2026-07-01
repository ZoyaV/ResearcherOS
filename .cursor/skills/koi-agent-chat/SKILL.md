---
name: koi-agent-chat
description: >-
  Answer questions sent from the ResearchOS UI chat panel. First use the project
  research question database (research.json); only read experiment reports when
  details are missing. Use when agent-chat queue has items or the user asks
  about a KOI UI question.
---

# KOI: вопрос из UI → ответ агента

Пользователь задаёт вопрос в панели **«Спросить агента»** на localhost:8080. Вопрос попадает в очередь `.run/agent-chat-queue.json`.

**Автоответ:** если вопрос хорошо совпадает с `research.json`, API отвечает сразу.

**Режим в настройках UI** (`Настройки → Агент в чате`):

| Режим | Поведение |
|-------|-----------|
| **Inbox-чат** (`cursor_inbox`, рекомендуется) | Watcher → `AGENT_CHAT_WAKE` в `.run/logs/agent-chat-watch.log` (~1–3 с) |
| **Hooks** (`cursor_ide`) | Очередь при старте/stop любого чата агента |
| **Фоновый API** (`api`) | Воркер + `CURSOR_API_KEY` |

Инструкция: `docs/agent/agent-chat-inbox.md`. Bootstrap: `python scripts/koi_agent_chat_inbox.py bootstrap`.

## Когда запускать

1. В очереди есть необработанные вопросы (проверь при старте сессии с KOI).
2. Hook `stop` прислал follow-up про agent-chat.
3. Пользователь явно ссылается на вопрос из ResearchOS UI.

```bash
KOI/.venv/bin/python KOI/scripts/koi_agent_chat.py pending
```

## Главное правило ответа

**Сначала база исследовательских вопросов, потом отчёты.**

| Шаг | Источник | Когда |
|-----|----------|-------|
| 1 | `projects/<id>/research.json` и поле `research_database` в context | **Всегда первым** — ищи релевантные записи по смыслу вопроса |
| 2 | `narrative` + `answer` из найденной записи | Формируй ответ пользователю; `narrative` — основной текст, `answer` — технические детали |
| 3 | Отчёт эксперимента (`experiment.report_path` / `report_markdown`) | **Только если** в базе нет подходящего ответа или пользователю нужны детали (цифры, графики, методология), которых нет в `narrative`/`answer` |
| 4 | `card_id` → канбан-карточка | Ссылка на источник вывода; не открывай отчёт «на всякий случай» |

Не читай все отчёты подряд. Не дублируй в ответе сырой markdown отчёта, если достаточно `narrative`.

Файл базы на диске: `projects/<project_id>/research.json` (см. также `research_database_path` в context).

## Workflow (на один вопрос)

### 0. Принять задачу (Inbox)

Сразу отметь вопрос принятым — UI покажет «прочитано» и анимацию «Агент пишет…»:

```bash
KOI/.venv/bin/python KOI/scripts/koi_agent_chat.py claim <queue_id>
```

### 1. Собрать контекст

```bash
KOI/.venv/bin/python KOI/scripts/koi_agent_chat.py context <queue_id>
```

В JSON:

- `user_question` — текст вопроса из UI
- `project_id`, `project_title`
- `scope_method` / `scope_node` — опциональный контекст (если пользователь был на методе/узле)
- `research_database` — **все** выводы по методам проекта (id, method_title, question, narrative, answer, certainty, importance, card_id, experiment.report_path)
- `answer_policy` — краткое напоминание политики

### 2. Ответить

1. Сопоставь `user_question` с записями `research_database` (по смыслу, не только по точному совпадению формулировки).
2. Если есть релевантные записи — раскрой тему **свободным связным текстом**: объедини факты, поясни нюансы, укажи ограничения (`definite` / `tentative`).
3. Если одной записи мало — уточни по `answer`, затем при необходимости прочитай **только** `experiment.report_path` для связанного `card_id`.
4. Если в базе ничего нет — честно скажи; предложи завершить эксперимент (done → koi-done-research) или уточни вопрос.
5. Учитывай `scope_method` / `scope_node`, но не ограничивай поиск только ими, если вопрос шире.

**Формат текста для UI** (см. `koi/agent_chat_format.py`):

- Основная часть — развёрнутый ответ по-русски, без лишних аббревиатур.
- В конце обязательно блок **«Источники:»** — список методов и экспериментов, на которых основан ответ:

```
Источники:
• Метод «…» → эксперимент «…»
• Метод «…» → эксперимент «…»
```

Используй `method_title` и `experiment.card_title` из `research_database`.

### 3. Отправить ответ в UI (обязательно)

Пользователь ждёт ответ **в панели ResearchOS**, не только в Cursor. После формулировки ответа:

```bash
KOI/.venv/bin/python KOI/scripts/koi_agent_chat.py answer <queue_id> "Текст ответа…"
```

Или длинный текст из файла:

```bash
KOI/.venv/bin/python KOI/scripts/koi_agent_chat.py answer <queue_id> -f /tmp/answer.md
```

Или API:

```bash
curl -s -X PATCH "http://127.0.0.1:8010/agent-chat/<queue_id>" \
  -H "Content-Type: application/json" \
  -d '{"answer": "Текст ответа…"}'
```

Без этого шага вопрос остаётся «в очереди» в интерфейсе. Не вызывай `answer`, если ждёшь уточнения от пользователя.

## Очередь и hooks

| Hook | Скрипт | Поведение |
|------|--------|-----------|
| `sessionStart` | `koi-agent-chat-session.sh` | `additional_context` со списком вопросов |
| `stop` | `koi-agent-chat-stop.sh` | `followup_message` — обработать следующий (приоритет над done-research) |

| API | Назначение |
|-----|------------|
| `POST /agent-chat` | вопрос из UI |
| `GET /agent-chat?project_id=` | история + статусы для UI |
| `PATCH /agent-chat/{id}` | ответ агента → показ в UI |

## Автозапуск агента (без открытого чата в IDE)

1. Создайте `KOI/.env`:
   ```
   CURSOR_API_KEY=ваш_ключ
   # опционально: KOI_AGENT_CHAT_MODEL=composer-2.5
   ```
2. `KOI/.venv/bin/pip install cursor-sdk`
3. `KOI/scripts/koi-serve.sh restart` — поднимет воркер, если ключ есть.

Вручную обработать очередь:
```bash
KOI/.venv/bin/python KOI/scripts/koi_agent_chat_worker.py --once
```

Без ключа в режиме `cursor_ide`: мгновенный ответ из `research.json`; остальное — hooks в IDE.

## Связанные скиллы

- База выводов пополняется через **koi-done-research** (карточка → done).
- Dev-сервер: **koi-dev-server** (8010 + 8080).
