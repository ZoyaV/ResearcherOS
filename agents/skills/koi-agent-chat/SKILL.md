---
name: koi-agent-chat
description: >-
  Answer questions sent from the ResearchOS UI chat panel. First use the project
  research question database (research.json); only read experiment reports when
  details are missing. Use when the agent-chat queue has items or the user asks
  about a KOI UI question.
---

# KOI: UI question → agent answer

The user asks a question in the **Ask the agent** panel at localhost:8080. The
question enters `.run/agent-chat-queue.json`.

**Automatic answer:** when a question closely matches `research.json`, the API
answers immediately.

**UI mode** (`Settings → Chat agent`):

| Mode | Behavior |
|------|----------|
| **Inbox chat** (`cursor_inbox`, recommended) | Watcher writes `AGENT_CHAT_WAKE` to `.run/logs/agent-chat-watch.log` in about 1–3 seconds |
| **Hooks** (`cursor_ide`) | Process the queue when any agent chat starts or stops |
| **Background API** (`api`) | Worker using `CURSOR_API_KEY` |

See `docs/agent-chat-inbox.md`. Bootstrap with
`python -m koi.agent_chat.inbox_cli bootstrap`.

## When to run

1. The queue contains unanswered questions; check it when starting a KOI session.
2. A `stop` hook sent an agent-chat follow-up.
3. The user explicitly refers to a question from the ResearchOS UI.

```bash
KOI/.venv/bin/python -m koi.agent_chat.cli pending
```

## Primary answer rule

**Use the research-question database first and reports second.**

| Step | Source | When |
|------|--------|------|
| 1 | `projects/<id>/research.json` and `research_database` in context | **Always first**: find entries relevant to the meaning of the question |
| 2 | `narrative` + `answer` from matching entries | Build the user answer; `narrative` is primary prose and `answer` contains technical detail |
| 3 | Experiment report (`experiment.report_path` / `report_markdown`) | **Only when** the database has no matching answer or the user needs numbers, figures, or methodology missing from `narrative`/`answer` |
| 4 | `card_id` → kanban card | Cite the conclusion source; do not open the report “just in case” |

Do not read every report. Do not repeat raw report Markdown when `narrative` is
enough.

The database file is `projects/<project_id>/research.json`; context also contains
`research_database_path`.

## Workflow for one question

### 0. Claim the item (Inbox)

Claim the question immediately so the UI shows Read and the Agent is typing
animation:

```bash
KOI/.venv/bin/python -m koi.agent_chat.cli claim <queue_id>
```

### 1. Gather context

```bash
KOI/.venv/bin/python -m koi.agent_chat.cli context <queue_id>
```

The JSON contains:

- `user_question` — question from the UI
- `project_id`, `project_title`
- `scope_method` / `scope_node` — optional context from the method/node being viewed
- `research_database` — every method conclusion in the project: id,
  method_title, question, narrative, answer, certainty, importance, card_id, and
  experiment.report_path
- `answer_policy` — compact policy reminder

### 2. Compose the answer

1. Match `user_question` to `research_database` semantically, not only by exact wording.
2. If relevant entries exist, explain them in **clear connected prose**: combine
   facts, explain nuances, and name `definite` / `tentative` limitations.
3. If one entry is insufficient, inspect `answer`; then, only if necessary, read
   the linked `experiment.report_path` for that `card_id`.
4. If the database has no answer, say so plainly and suggest completing the
   relevant experiment (done → koi-done-research) or narrowing the question.
5. Respect `scope_method` / `scope_node`, but search beyond them when the question
   is broader.

**UI text format** (see `koi/agent_chat/formatting.py`):

- The main part is a complete answer in natural English with minimal jargon.
- End with a mandatory **Sources:** block listing the methods and experiments
  that support the answer:

```text
Sources:
• Method “…” → experiment “…”
• Method “…” → experiment “…”
```

Use `method_title` and `experiment.card_title` from `research_database`.

### 3. Send the answer to the UI (required)

The user is waiting in ResearchOS, not only in Cursor. After composing the answer:

```bash
KOI/.venv/bin/python -m koi.agent_chat.cli answer <queue_id> "Answer text…"
```

For long text from a file:

```bash
KOI/.venv/bin/python -m koi.agent_chat.cli answer <queue_id> -f /tmp/answer.md
```

Or through the API:

```bash
curl -s -X PATCH "http://127.0.0.1:8010/agent-chat/<queue_id>" \
  -H "Content-Type: application/json" \
  -d '{"answer": "Answer text…"}'
```

Without this step, the UI still shows the question as queued. Do not call
`answer` while waiting for user clarification.

## Queue and hooks

Scripts live in `agents/skills/koi-agent-chat/hooks/`. IDE configuration:
`.cursor/hooks.json` from `agents/cursor-hooks.json`.

| Hook | Script | Behavior |
|------|--------|----------|
| `sessionStart` | `koi-agent-chat-session.sh` | Adds the question list through `additional_context` |
| `stop` | `koi-agent-chat-stop.sh` | Sends a `followup_message` to process the next item, ahead of done-research |

| API | Purpose |
|-----|---------|
| `POST /agent-chat` | Submit a question from the UI |
| `GET /agent-chat?project_id=` | UI history and statuses |
| `PATCH /agent-chat/{id}` | Send the agent answer to the UI |

## Start an agent without an open IDE chat

1. Create `KOI/.env`:
   ```
   CURSOR_API_KEY=your_key
   # optional: KOI_AGENT_CHAT_MODEL=composer-2.5
   ```
2. Run `KOI/.venv/bin/pip install cursor-sdk`.
3. Run `KOI/scripts/koi-serve.sh restart`; it starts the worker when the key is present.

Process the queue manually:

```bash
KOI/.venv/bin/python -m koi.agent_chat.worker --once
```

Without a key in `cursor_ide` mode, matching questions still receive immediate
answers from `research.json`; the IDE hooks handle the rest.

## Related skills

- **koi-done-research** adds conclusions to the database when a card reaches done.
- **koi-dev-server** manages the development server on ports 8010 and 8080.
