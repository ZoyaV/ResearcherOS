# ResearchOS Inbox — three Cursor chats

In **`cursor_inbox`** mode, three separate chats use **watchers** to wake agents through log wake lines (about 1–3 seconds).

| Chat | UI page | Log | Tag |
|-----|-------------|-----|-----|
| **ResearchOS Chat Inbox** | Ask Agent panel | `.run/logs/agent-chat-watch.log` | `AGENT_CHAT_WAKE` |
| **ResearchOS Literature Inbox** | literature.html → Related Work | `.run/logs/related-work-watch.log` | `RELATED_WORK_WAKE` |
| **ResearchOS Paper Inbox** | index.html → Paper | `.run/logs/paper-watch.log` | `PAPER_WAKE` |

## Quick start (once per chat)

### Chat Inbox

1. UI Settings → **Inbox chat** → Save.
2. Run `./scripts/koi-serve.sh start` to start all three watchers.
3. Create a **ResearchOS Chat Inbox** chat in Cursor.
4. On the main page, click **Copy message for Cursor**, paste it into chat, and send it.
5. The agent listens to `tail -f .run/logs/agent-chat-watch.log` using the `^AGENT_CHAT_WAKE` regex.
6. Click **Inbox ready** in the chat panel.

### Literature Inbox

1. Open **literature.html** → Related Work.
2. Create a **ResearchOS Literature Inbox** chat in Cursor.
3. Copy the bootstrap message from the literature page and paste it into chat.
4. The agent listens to `tail -f .run/logs/related-work-watch.log` using the `^RELATED_WORK_WAKE` regex.
5. Click **Inbox ready** on the literature page.

### Paper Inbox

1. Open a project in **index.html** → **Paper** modal.
2. Create a **ResearchOS Paper Inbox** chat in Cursor.
3. Copy the bootstrap message from the modal and paste it into chat.
4. The agent listens to `tail -f .run/logs/paper-watch.log` using the `^PAPER_WAKE` regex.
5. Click **Inbox ready** in the paper modal.

## Commands

```bash
# Chat
.venv/bin/python -m koi.agent_chat.inbox_cli watch
.venv/bin/python -m koi.agent_chat.inbox_cli pending
.venv/bin/python -m koi.agent_chat.inbox_cli bootstrap

# Literature / Related Work
.venv/bin/python -m koi.related_work.inbox_cli watch
.venv/bin/python -m koi.related_work.inbox_cli pending
.venv/bin/python -m koi.related_work.inbox_cli bootstrap

# Paper
.venv/bin/python -m koi.paper.inbox_cli watch
.venv/bin/python -m koi.paper.inbox_cli pending
.venv/bin/python -m koi.paper.inbox_cli bootstrap
```

On macOS without `inotifywait`, each watcher polls its queue every two seconds.
