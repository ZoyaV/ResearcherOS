# ResearchOS knowledge base — structure and use

User documentation. In brief, every project has a knowledge base that is
**assembled automatically** from project data. An agent (Claude Code or Cursor)
can test hypotheses and write a report from the template; the report is then
converted into new knowledge automatically. The knowledge base is not assembled manually.

Related documents: process and review matrix in `docs/research-workflow.md`;
agent-work overview in `docs/agents.md`; project format in `docs/human/project-format.md`.

## 1. What the project knowledge base is for

The goal is to **reuse accumulated experience instead of rediscovering it**. A
new person or agent can learn in minutes what is already known, which hypotheses
were tested, and what happened; each new experiment expands that context.

Structure inside the project directory `projects/<id>/`:

```
projects/<id>/
  project.md         hypothesis tree + kanban + verdicts   ← source of truth
  research.json      insights (Q&A, ≤3 per method)          ← source of truth
  reports/           experiment reports (+ index.json: card_id → path)
  KNOWLEDGE.md       knowledge-base CONTENTS: statistics, document summaries + links,
                     hypothesis status and findings         [generated]
  KNOWLEDGE_LOG.md   update log: what was recorded and when [generated]
  knowledge/         full knowledge documents:
    hypotheses.md    hypotheses + verdicts + insights + report links [generated]
    NN-name.md       curated documents: overview, setup, launch,
                     scripts, pitfalls, open questions…     [written by a human/agent]
```

Do not edit files marked [generated] manually; the `koi/knowledge/` core module
rebuilds them. The sources of truth are `project.md`, `research.json`, and `knowledge/*.md`.

## 2. What happens automatically

1. **Every project save**, through the API, UI, or `save_project` in code, runs a
   hook that rebuilds `knowledge/hypotheses.md` and the `KNOWLEDGE.md` contents,
   then appends exact changes to `KNOWLEDGE_LOG.md` (verdict changes, new or
   updated insights, new documents). The diff is computed against
   `knowledge/.state.json`; a rebuild with no changes creates no entries.
2. **A new `.md` in `knowledge/`** is discovered on the next project save or
   `GET /projects/{id}/knowledge` request, then appears in the contents and log.
3. **An agent's hypothesis-test report** (`.run.md`) is parsed automatically and
   converted into a verdict, insights, and a move of the card to done (section 4).
4. Each project's index is updated automatically through `koi/knowledge`.

## 3. How to view the knowledge base

**Web interface**: open a project → Knowledge Base. The Knowledge tab is a
dashboard with counters (supported/refuted/open hypotheses, insights, documents,
reports), verdict progress, hypothesis cards with verdicts and insights
(importance ●●●○○, definite/tentative certainty, report link), knowledge-document
tiles, and recent log entries. Clicking a document/report opens it in the same
modal; the Update Log tab contains the full log.

**Files**: start with `projects/<id>/KNOWLEDGE.md` and follow its links.

**API** (our instance uses :8011, or :8010 through the tunnel):
- `GET /projects/{id}/knowledge` — Markdown contents; rebuilds the knowledge base on request;
- `GET /projects/{id}/knowledge/summary` — structured JSON rendered by the dashboard;
- `GET /projects/{id}/knowledge/log` — log; `…/knowledge/file?path=…` — any project .md;
- `GET /agent/backends` — available agent backends and their order.

## 4. Automatic hypothesis testing by an agent → new knowledge

Run the complete cycle with one command from the repository root inside `.venv`:

```bash
python -m koi.projects.report_ingest.cli <project_id> <card_id>
```

What happens:
1. The script finds the card, collects context (problem→…→method node chain,
   card description, existing insights), and prepares an agent task with strict
   report requirements (all §§0–5 of
   `agents/skills/koi-report-review/experiment-report.md`).
2. The agent (Claude Code CLI or Cursor SDK; see section 5) performs the test and
   writes `reports/<node>/<card>.run.md`. It must change nothing except the report file.
3. `koi/projects/report_ingest/` automatically ingests the report: §5.1 supplies
   the hypothesis verdict and §5.2 supplies a JSON block of no more than three
   research.json insights. It updates the node verdict, research.json, card → done,
   and `reports/index.json`; the `save_project` hook rebuilds the knowledge base and log.

Useful flags: `--backend claude|cursor` (force a backend), `--no-ingest` (report
only), `--dry-run` (show prospective changes), `--ingest-only [path]` (ingest an
existing report without an agent, including human-written reports), and `--timeout N`.

**Report requirements for automatic integration** (passed to the agent
automatically and required for a hand-written `.run.md`):
- §0 “References” — table with exact IDs for the cause hypothesis, method, and card;
- §5.1 — `` `<node-id>` → … **supported|refuted|open** `` (takes precedence over §0);
- §5.2 — exactly one fenced ```json block with an array of no more than three insights, fields:
  `method_id, card_id, question, answer, narrative, certainty (definite|tentative),
  importance (1–5)`; `id` is optional and defaults to `rq-<card_id>-<n>`.

Ingestion is idempotent: ingesting the same report again changes nothing. Insights
from that card are replaced, while insights from other cards remain.

## 5. Agent backends: Claude Code and Cursor

Both hypothesis testing and agent chat (the UI question queue) use
`koi/adapters/agent_backends.py`. Backends are tried in order and unavailable ones are skipped.

| Variable | Default | Meaning |
|---|---|---|
| `KOI_AGENT_BACKEND` | `claude,cursor` | backend order; `off` disables agents |
| `KOI_CLAUDE_BIN` | `claude` | path to Claude Code CLI |
| `KOI_CLAUDE_MODEL` | CLI default | model for `claude -p` |
| `KOI_CLAUDE_ARGS` | — | additional CLI arguments |
| `KOI_CLAUDE_ALLOWED_TOOLS` | `Read,Glob,Grep,Bash,Write,Edit` | tools available when edits are allowed |
| `CURSOR_API_KEY` | — | Cursor key; without it the Cursor backend is unavailable |
| `KOI_AGENT_CHAT_MODEL` | `composer-2.5` | Cursor SDK model |

**To enable Claude Code**, install the CLI (`npm install -g @anthropic-ai/claude-code`)
and authenticate with `claude login` or `ANTHROPIC_API_KEY`.
**To enable Cursor**, run `pip install cursor-sdk` in `.venv` and set `CURSOR_API_KEY`.
Check readiness with `GET /agent/backends` or
`PYTHONPATH=. python -c "from koi.adapters.agent_backends import backend_status; print(backend_status())"`.

Claude Code runs headlessly as `claude -p --output-format text`, with the prompt
on stdin. Hypothesis tests add `--permission-mode acceptEdits` and allowed tools
so the agent can write the report file.

## 6. How to add knowledge manually

- **Knowledge document**: place `NN-name.md` in `projects/<id>/knowledge/`.
  Convention: first line `# Title`, first paragraph a one-to-two-sentence summary
  for the contents. It appears in the knowledge base automatically.
- **Direct verdict/insight**: edit `project.md` (`verdict:` below a node) or
  `research.json`, then save the project; the hook updates the knowledge base and log.
- **Completed report**: write `.run.md` from the template and use `--ingest-only`
  (section 4). This is preferred because verdict and insights pass through one validator.

## 7. Pipeline self-check

The main pytest suite checks knowledge and report-ingest behavior:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_knowledge.py tests/test_report_ingest.py
```
