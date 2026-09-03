# Research Chat

<p class="lead">The local **Ask agent** panel queues a question, answers from <code>research.json</code> first, and reads reports only when details are missing. Delivery uses a Cursor Inbox, IDE hooks, or a background API.</p>

<div class="media-slot" data-media="chat-hero" data-accept="png,jpg,webp,mp4,webm"><p>Media: Research Chat</p></div>

## How it works

A question is not sent indiscriminately to the entire repository. The answer policy is:

1. Match the question against `research.json` entries: question, human narrative, concise technical answer, certainty, importance, and source card.
2. Compose an answer from relevant entries.
3. Open an experiment report only when figures or method details are missing.
4. If the database is empty, say so and suggest completing an experiment or clarifying the question.

A strong match may be answered immediately by the API. Delivery modes under **Settings → Chat agent** are Cursor Inbox (recommended, 1–3 second wake signal), IDE hooks, and a background worker using a Cursor API key. The queue is `.run/agent-chat-queue.json`; `koi-agent-chat` performs claim → context → answer → complete.

## How people use the interface

1. Open a project and the chat panel.
2. For first-time Inbox setup, copy the bootstrap message into **ResearchOS Chat Inbox** in Cursor and click **Inbox ready**.
3. Submit a question. The feed shows queued, read, and writing states before the answer.
4. Scope may include the current method or node without removing access to the project database.
5. Switch to hooks or API mode in Settings when needed. Missing Inbox or API setup produces an explicit instruction.

## Agent workflows

- `koi-agent-chat`: main queue workflow and research-first answer policy.
- `koi-done-research`: populates the findings the chat uses.
- `koi-knowledge-curator`: adds curated context but does not replace `research.json` as the first source.
- `agents/skills/koi-agent-chat/hooks/`: session/stop hooks for IDE mode.

```bash
python -m koi.agent_chat.cli pending
python -m koi.agent_chat.cli claim <queue_id>
python -m koi.agent_chat.cli context <queue_id>
python -m koi.agent_chat.inbox_cli bootstrap
python -m koi.agent_chat.inbox_cli watch
```

## Technical details and limits

UI → queue API → optional automatic finding match → watcher/hook/worker → agent claim and context → answer API → panel. Code lives in `koi/agent_chat/`; the client panel is in `web/index.html` and `web/app.js`. Context may include `scope_method` and `scope_node`.

Chat does not replace onboarding or write the tree. Answer quality depends on findings and reports. On macOS without inotify, Inbox polls about every two seconds and requires `koi-serve` or the watcher.

Related: [Knowledge base](knowledge.html) · [Experiment kanban](kanban.html) · [Architecture](index.html) · [Related Work](related-work.html) · [PaperDraft](paper.html)
