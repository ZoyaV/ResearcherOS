# ResearchOS Inbox — три чата Cursor

Режим **`cursor_inbox`**: три отдельных чата с **watcher**, которые будят агентов через wake-строки в логах (~1–3 с).

| Чат | Страница UI | Лог | Тег |
|-----|-------------|-----|-----|
| **ResearchOS Chat Inbox** | Панель «Спросить агента» | `.run/logs/agent-chat-watch.log` | `AGENT_CHAT_WAKE` |
| **ResearchOS Literature Inbox** | literature.html → Related Work | `.run/logs/related-work-watch.log` | `RELATED_WORK_WAKE` |
| **ResearchOS Paper Inbox** | index.html → «Статья» | `.run/logs/paper-watch.log` | `PAPER_WAKE` |

## Быстрый старт (один раз на каждый чат)

### Chat Inbox

1. Настройки UI → **Inbox-чат** → Сохранить.
2. `./scripts/koi-serve.sh start` — поднимает все три watcher.
3. Создайте чат **ResearchOS Chat Inbox** в Cursor.
4. На главной: **Скопировать сообщение для Cursor** → вставить в чат → отправить.
5. Агент слушает `tail -f .run/logs/agent-chat-watch.log` по regex `^AGENT_CHAT_WAKE`.
6. Нажмите **«Inbox готов»** в панели чата.

### Literature Inbox

1. Откройте **literature.html** → Related Work.
2. Создайте чат **ResearchOS Literature Inbox** в Cursor.
3. Скопируйте bootstrap (кнопка на странице литературы) → вставьте в чат.
4. Агент слушает `tail -f .run/logs/related-work-watch.log` по regex `^RELATED_WORK_WAKE`.
5. Нажмите **«Inbox готов»** на странице литературы.

### Paper Inbox

1. Откройте проект в **index.html** → модалка **«Статья»**.
2. Создайте чат **ResearchOS Paper Inbox** в Cursor.
3. Скопируйте bootstrap (кнопка в модалке) → вставьте в чат.
4. Агент слушает `tail -f .run/logs/paper-watch.log` по regex `^PAPER_WAKE`.
5. Нажмите **«Inbox готов»** в модалке статьи.

## Команды

```bash
# Чат
.venv/bin/python scripts/koi_agent_chat_inbox.py watch
.venv/bin/python scripts/koi_agent_chat_inbox.py pending
.venv/bin/python scripts/koi_agent_chat_inbox.py bootstrap

# Литература / Related Work
.venv/bin/python scripts/koi_related_work_inbox.py watch
.venv/bin/python scripts/koi_related_work_inbox.py pending
.venv/bin/python scripts/koi_related_work_inbox.py bootstrap

# Статья / Paper
.venv/bin/python scripts/koi_paper_inbox.py watch
.venv/bin/python scripts/koi_paper_inbox.py pending
.venv/bin/python scripts/koi_paper_inbox.py bootstrap
```

На macOS без `inotifywait` каждый watcher поллит свою очередь каждые 2 с.
