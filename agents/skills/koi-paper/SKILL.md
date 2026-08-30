---
name: koi-paper
description: >-
  Generate a NeurIPS paper (LaTeX → PDF) from the ResearchOS paper queue.
  Use when paper-queue.json has pending items or `koi.paper.cli pending` lists tasks.
---

# KOI: paper from the UI → project PDF

The user clicked **Generate paper** in the Paper modal on index.html. The task
entered `.run/paper-queue.json`.

## When to run

1. The queue contains a pending paper (`python -m koi.paper.cli pending`).
2. Paper Inbox received `PAPER_WAKE` in `.run/logs/paper-watch.log`.
3. The user pasted “ResearchOS Paper Inbox — paper `paper-…`.”

```bash
ReseachOS/.venv/bin/python -m koi.paper.cli pending
```

Or inspect Paper Inbox:

```bash
ReseachOS/.venv/bin/python -m koi.paper.inbox_cli pending
```

## Algorithm

0. **Immediately** claim the task so the UI shows Agent is working:

```bash
ReseachOS/.venv/bin/python -m koi.paper.cli claim <queue_id>
```

1. Run `context <queue_id>` to obtain JSON with the full prompt and project data
   (hypothesis tree, research.json, reports, and figures).
2. Write the paper **in English** using LaTeX. The response format is mandatory:

```text
TITLE: <concise scientific paper title in English>
===LATEX===
<LaTeX body only — abstract through bibliography, no \documentclass or \begin{document}>
```

Follow the LaTeX rules in the context `prompt`. Use only figure paths included
in that prompt.

3. **Always** return the result to the system, which builds main.tex and the PDF:

```bash
ReseachOS/.venv/bin/python -m koi.paper.cli answer <queue_id> -f paper-body.txt
```

Without `claim`, the UI remains Waiting for request. Without `answer`, no PDF
appears. If compilation fails, fix the LaTeX and run `answer` again, or report
the issue to the user.

## Paper Inbox (recommended)

Use a dedicated persistent **ResearchOS Paper Inbox** Cursor chat only for paper
generation.

1. Once: run `python -m koi.paper.inbox_cli bootstrap` and paste the result into
   **ResearchOS Paper Inbox**.
2. The bootstrap starts a background `tail -f` with `notify_on_output` matching
   `^PAPER_WAKE`, plus a fallback loop (`AGENT_LOOP_TICK_PAPER`) every five seconds.
3. `koi-serve.sh start` launches the watcher; wake appears in about 1–3 seconds.
4. **Generate paper** → queue → Paper Inbox wake → **claim → context → answer**.

Manual message copying is unnecessary after Paper Inbox is configured. For
first-time setup, use the button in the Paper modal to copy the bootstrap and
then mark Inbox ready.
