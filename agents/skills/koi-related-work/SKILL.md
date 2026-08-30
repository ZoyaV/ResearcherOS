---
name: koi-related-work
description: >-
  Generate Related Work markdown from the ResearchOS RelatedWork page queue.
  Use when related-work-queue.json has pending items or
  `koi.related_work.cli pending` lists tasks.
---

# KOI: Related Work from the UI → RelatedWork response

The user clicked **Related Work** on the RelatedWork page at
localhost:8080/literature.html. The task entered `.run/related-work-queue.json`.

## When to run

1. The queue contains pending Related Work (`python -m koi.related_work.cli pending`).
2. Literature Inbox received `RELATED_WORK_WAKE` in `.run/logs/related-work-watch.log`.
3. The user pasted “ResearchOS Literature Inbox — Related Work `rw-…`.”

```bash
ReseachOS/.venv/bin/python -m koi.related_work.cli pending
```

Or inspect Literature Inbox:

```bash
ReseachOS/.venv/bin/python -m koi.related_work.inbox_cli pending
```

## Algorithm

0. **Immediately** claim the task so the UI shows Agent is working and starts
   the timer:

```bash
ReseachOS/.venv/bin/python -m koi.related_work.cli claim <queue_id>
```

1. Run `context <queue_id>` to obtain JSON with the full prompt and cluster metadata.
2. Write a Markdown **Related Work** section:
   - heading `## Related Work`
   - 2–5 paragraphs synthesizing the selected clusters
   - facts from the prompt only; never invent papers
3. **Always** save the answer to the UI:

```bash
ReseachOS/.venv/bin/python -m koi.related_work.cli answer <queue_id> -f related-work.md
```

Without `claim`, the page remains Waiting for request. Without `answer`, no draft
appears.

## Literature Inbox (recommended)

Use a dedicated persistent **ResearchOS Literature Inbox** Cursor chat only for
Related Work, separate from the Chat Inbox used for questions.

1. Once: run `python -m koi.related_work.inbox_cli bootstrap` and paste the result
   into **ResearchOS Literature Inbox**.
2. The bootstrap starts a background `tail -f` with `notify_on_output` matching
   `^RELATED_WORK_WAKE`, plus a fallback loop (`AGENT_LOOP_TICK_RELATED_WORK`)
   every three seconds and `python -m koi.related_work.inbox_cli pending`.
3. `koi-serve.sh start` launches the watcher; wake appears in about 1–3 seconds.
4. Clicking **Related Work** queues the task; on wake, Literature Inbox performs
   **claim → context → answer**.

Manual message copying is unnecessary after Literature Inbox is configured.

For first-time setup, use Copy message on literature.html; the UI shows only the
instructions, not the message body.
